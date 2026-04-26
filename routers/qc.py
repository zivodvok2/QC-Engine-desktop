import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from checks.logic_checks import LogicCheck
from core.cleaner import DataCleaner
from core.loader import DataLoader
from core.reporter import Reporter
from core.rule_engine import RuleEngine
from job_store import REPORTS_DIR, file_store, job_store
from schemas import (
    ColumnsResponse,
    LogicValidateRequest,
    RunRequest,
    RunResponse,
    StatusResponse,
    UploadResponse,
)

router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _df_to_records(df) -> List[Dict[str, Any]]:
    """Serialize a DataFrame to JSON-safe list of dicts."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _serialize_qc_results(qc_results) -> Dict[str, Any]:
    checks = []
    total_flags = 0
    flagged_by_severity: Dict[str, int] = {"critical": 0, "warning": 0, "info": 0}

    for result in qc_results:
        try:
            rows_json = _df_to_records(result.flagged_rows)
        except Exception:
            rows_json = []

        checks.append(
            {
                "check_name": result.check_name,
                "issue_type": result.issue_type,
                "severity": result.severity,
                "flag_count": result.flag_count,
                "flagged_rows": rows_json,
            }
        )
        total_flags += result.flag_count
        sev = result.severity if result.severity in flagged_by_severity else "info"
        flagged_by_severity[sev] += result.flag_count

    return {
        "total_flags": total_flags,
        "flagged_by_severity": flagged_by_severity,
        "checks": checks,
    }


def _sync_pipeline(file_path: Path, config: dict, job_id: str):
    """Runs the full Load → Clean → Validate → Report pipeline synchronously.
    Called from a thread-pool executor so it doesn't block the event loop.
    """
    loader = DataLoader()
    cleaner = DataCleaner()

    df = loader.load(str(file_path))
    df_clean = cleaner.clean(df)

    # Inject user-supplied Groq key if present
    user_groq_key = (config.get("verbatim_check") or {}).get("groq_api_key", "")
    _old_groq = os.environ.get("GROQ_API_KEY")
    if user_groq_key:
        os.environ["GROQ_API_KEY"] = user_groq_key

    try:
        engine = RuleEngine(config=config)
        results = engine.run(df_clean)
    finally:
        if user_groq_key:
            if _old_groq is not None:
                os.environ["GROQ_API_KEY"] = _old_groq
            else:
                os.environ.pop("GROQ_API_KEY", None)

    serialized = _serialize_qc_results(results)

    # Generate Excel report into a job-specific temp directory
    report_dir = REPORTS_DIR / job_id
    report_dir.mkdir(parents=True, exist_ok=True)
    reporter = Reporter(output_dir=str(report_dir))
    reporter.generate(results, df_clean)

    xlsx_files = list(report_dir.glob("qc_summary_*.xlsx"))
    report_path = str(xlsx_files[0]) if xlsx_files else None

    return serialized, report_path


def _sync_logic_check(file_path: Path, rules: list) -> Dict[str, Any]:
    loader = DataLoader()
    cleaner = DataCleaner()
    df = cleaner.clean(loader.load(str(file_path)))

    check = LogicCheck(rules=rules)
    result = check.run(df)

    try:
        rows_json = _df_to_records(result.flagged_rows)
    except Exception:
        rows_json = []

    return {"violation_count": result.flag_count, "flagged_rows": rows_json}


# ── Background task ────────────────────────────────────────────────────────────

async def _run_qc_background(job_id: str, file_path: Path, config: dict):
    await job_store.update(job_id, status="running", progress=10)
    try:
        loop = asyncio.get_running_loop()
        serialized, report_path = await loop.run_in_executor(
            None, _sync_pipeline, file_path, config, job_id
        )
        await job_store.update(
            job_id,
            status="complete",
            progress=100,
            results=serialized,
            report_path=report_path,
        )
    except Exception as exc:
        await job_store.update(job_id, status="failed", error=str(exc), progress=0)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"},
        )

    file_id = str(uuid.uuid4())
    from job_store import UPLOAD_DIR

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / f"{file_id}{ext}"

    content = await file.read()
    file_path.write_bytes(content)

    try:
        loader = DataLoader()
        df = loader.load(str(file_path))
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail={"error": str(exc)})

    await file_store.put(file_id, file_path)

    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "",
        rows=len(df),
        columns=len(df.columns),
        column_names=df.columns.tolist(),
    )


@router.post("/run", response_model=RunResponse)
async def run_qc(req: RunRequest, background_tasks: BackgroundTasks):
    file_path = await file_store.get(req.file_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail={"error": "file_id not found or file has expired"})

    job_id = str(uuid.uuid4())
    await job_store.create(job_id, req.file_id)
    background_tasks.add_task(_run_qc_background, job_id, file_path, req.config)

    return RunResponse(job_id=job_id, status="queued")


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    job = await job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_id not found"})
    return StatusResponse(job_id=job_id, status=job.status, progress=job.progress, error=job.error)


@router.get("/results/{job_id}")
async def get_results(job_id: str):
    job = await job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_id not found"})
    if job.status == "failed":
        raise HTTPException(status_code=500, detail={"error": job.error or "Job failed"})
    if job.status != "complete":
        raise HTTPException(
            status_code=409,
            detail={"error": f"Job not complete yet (status: {job.status})"},
        )
    return {"job_id": job_id, **(job.results or {})}


@router.get("/report/{job_id}")
async def get_report(job_id: str):
    job = await job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_id not found"})
    if job.status == "failed":
        raise HTTPException(status_code=500, detail={"error": job.error or "Job failed"})
    if job.status != "complete":
        raise HTTPException(
            status_code=409,
            detail={"error": f"Job not complete yet (status: {job.status})"},
        )
    if not job.report_path or not Path(job.report_path).exists():
        raise HTTPException(status_code=404, detail={"error": "Report file not found"})

    return FileResponse(
        path=job.report_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"qc_report_{job_id}.xlsx",
    )


@router.post("/logic/validate")
async def validate_logic(req: LogicValidateRequest):
    file_path = await file_store.get(req.file_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail={"error": "file_id not found or file has expired"})

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _sync_logic_check, file_path, req.rules)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    return result


@router.get("/columns/{file_id}", response_model=ColumnsResponse)
async def get_columns(file_id: str):
    file_path = await file_store.get(file_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail={"error": "file_id not found or file has expired"})

    try:
        loader = DataLoader()
        df = loader.load(str(file_path))
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})

    return ColumnsResponse(
        columns=df.columns.tolist(),
        dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
        sample=_df_to_records(df.head(5)),
    )
