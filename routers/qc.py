import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from checks.logic_checks import LogicCheck
from core.cleaner import DataCleaner
from core.loader import DataLoader
from core.reporter import Reporter, append_supplemental_sheet
from core.rule_engine import RuleEngine
from job_store import REPORTS_DIR, file_store, job_store
from schemas import (
    ColumnsResponse,
    LogicValidateRequest,
    RunRequest,
    RunResponse,
    StatusResponse,
    SupplementalRequest,
    UploadResponse,
)

router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _df_to_records(df) -> List[Dict[str, Any]]:
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

        checks.append({
            "check_name": result.check_name,
            "issue_type": result.issue_type,
            "severity": result.severity,
            "flag_count": result.flag_count,
            "flagged_rows": rows_json,
        })
        total_flags += result.flag_count
        sev = result.severity if result.severity in flagged_by_severity else "info"
        flagged_by_severity[sev] += result.flag_count

    return {
        "total_flags": total_flags,
        "flagged_by_severity": flagged_by_severity,
        "checks": checks,
    }


def _sync_validate(file_path: Path, config: dict, groq_key: str = ""):
    """Load → Clean → Validate. Returns (serialized, results, df_clean)."""
    loader = DataLoader()
    cleaner = DataCleaner()
    df = loader.load(str(file_path))
    df_clean = cleaner.clean(df)

    _old_groq = os.environ.get("GROQ_API_KEY")
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key
    try:
        engine = RuleEngine(config=config)
        results = engine.run(df_clean)
    finally:
        if groq_key:
            if _old_groq is not None:
                os.environ["GROQ_API_KEY"] = _old_groq
            else:
                os.environ.pop("GROQ_API_KEY", None)

    serialized = _serialize_qc_results(results)
    return serialized, results, df_clean


def _sync_generate_report(job_id: str, results, df_clean, supplemental: list) -> str:
    report_dir = REPORTS_DIR / job_id
    report_dir.mkdir(parents=True, exist_ok=True)
    # Remove stale reports before writing fresh one
    for old in report_dir.glob("qc_summary_*.xlsx"):
        try:
            old.unlink()
        except Exception:
            pass
    reporter = Reporter(output_dir=str(report_dir))
    return reporter.generate(results, df_clean, supplemental=supplemental)


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
        groq_key = (config.get("verbatim_check") or {}).get("groq_api_key", "")
        loop = asyncio.get_running_loop()

        serialized, results, df_clean = await loop.run_in_executor(
            None, _sync_validate, file_path, config, groq_key
        )

        # Store results + config (needed for report regen when supplemental added later)
        await job_store.update(
            job_id,
            status="complete",
            progress=100,
            results=serialized,
            config=config,
        )

        # Generate initial report
        job = await job_store.get(job_id)
        supplemental = job.supplemental_checks if job else []

        report_path = await loop.run_in_executor(
            None, _sync_generate_report, job_id, results, df_clean, supplemental
        )
        await job_store.update(job_id, report_path=report_path, report_stale=False)

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


@router.post("/job/{job_id}/supplemental")
async def add_supplemental(job_id: str, req: SupplementalRequest):
    """Append an ad-hoc tab check result as a sheet in the existing Excel report."""
    job = await job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_id not found"})
    if job.status not in ("complete", "failed"):
        raise HTTPException(status_code=409, detail={"error": "Job not complete yet"})

    entry = {
        "check_name":  req.check_name,
        "issue_type":  req.issue_type,
        "severity":    req.severity,
        "flag_count":  req.flag_count,
        "flagged_rows": req.flagged_rows,
    }
    updated = [e for e in job.supplemental_checks if e.get("check_name") != req.check_name] + [entry]
    await job_store.update(job_id, supplemental_checks=updated)

    # Append sheet directly into the cached Excel — no full pipeline re-run needed
    report_path = job.report_path
    if report_path and Path(report_path).exists():
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, append_supplemental_sheet, report_path, entry)
        except Exception as exc:
            import logging
            logging.getLogger("qc_router").warning(f"Sheet append failed for {job_id}: {exc}")

    return {"status": "ok", "supplemental_count": len(updated)}


@router.get("/report/{job_id}")
async def get_report(job_id: str):
    job = await job_store.get(job_id)

    # Resolve the report path — check in-memory job first, then disk (survives restarts)
    report_path: Optional[Path] = None
    if job is not None and job.report_path and Path(job.report_path).exists():
        report_path = Path(job.report_path)
    else:
        # Disk fallback: find the most-recently-written xlsx for this job_id
        report_dir = REPORTS_DIR / job_id
        if report_dir.exists():
            candidates = sorted(
                report_dir.glob("qc_summary_*.xlsx"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                report_path = candidates[0]

    if job is None and report_path is None:
        raise HTTPException(status_code=404, detail={"error": "job_id not found"})
    if job is not None and job.status == "failed":
        raise HTTPException(status_code=500, detail={"error": job.error or "Job failed"})
    if job is not None and job.status != "complete" and report_path is None:
        raise HTTPException(
            status_code=409,
            detail={"error": f"Job not complete yet (status: {job.status})"},
        )
    if report_path is None:
        raise HTTPException(status_code=404, detail={"error": "Report file not found"})

    return FileResponse(
        path=str(report_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"qc_report_{job_id[:8]}.xlsx",
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
