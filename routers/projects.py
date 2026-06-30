import asyncio
import json
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import shared_db
from routers.auth import get_current_user

# Roles that may save results and create projects
_SAVE_ROLES = {"qc_executive", "operations_manager", "qc_officer", "project_manager", "researcher"}

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str


class SaveQCRequest(BaseModel):
    file_id: str
    filename: str
    wave_label: Optional[str] = None
    job_id: Optional[str] = None
    column_config: Optional[dict[str, str]] = None
    interviewer_name_col: Optional[str] = None
    interviewer_supervisor_col: Optional[str] = None


# Column map: uppercase source column → dashboard schema column
_COL_MAP = {
    "INSTANCE_ID": "instance_id",
    "INSTANCE ID": "instance_id",
    "INTERVIEWER_ID": "interviewer_id",
    "INTERVIEWER ID": "interviewer_id",
    "INTERVIEW_DATE": "interview_date",
    "INTERVIEW DATE": "interview_date",
    "INTERVIEW_START_TIME": "start_time",
    "INTERVIEW START TIME": "start_time",
    "START_TIME": "start_time",
    "INTERVIEW_END_TIME": "end_time",
    "INTERVIEW END TIME": "end_time",
    "END_TIME": "end_time",
    "DURATION_MINUTES": "duration_minutes",
    "DURATION MINUTES": "duration_minutes",
    "DURATION_FLAG": "duration_flag",
    "DURATION FLAG": "duration_flag",
    "DURATION_VALIDATION": "duration_validation",
    "STRAIGHT_LINING": "straight_lining",
    "STRAIGHT-LINING": "straight_lining",
    "LONG_PAUSE": "long_pause",
    "LONG PAUSE": "long_pause",
    "GPS_STATUS": "gps_status",
    "PHONE_PRESENT": "phone_present",
    "AUDIO_PRESENT": "audio_present",
    "REGION": "region",
    "LOCATION": "location",
    "SAMPLE_POINT_ID": "sample_point_id",
    "SAMPLE POINT ID": "sample_point_id",
    "APPROVAL_STATUS": "approval_status",
    "QC_COMMENTS": "qc_comments",
}

# Header aliases for interviewer name / supervisor columns — used to auto-detect
# registry-enrichment columns when the caller doesn't explicitly pick them.
_INTERVIEWER_NAME_ALIASES = {
    "INTERVIEWER_NAME", "INTERVIEWER NAME",
    "ENUMERATOR_NAME", "ENUMERATOR NAME",
    "FIELDWORKER_NAME", "FIELDWORKER NAME",
    "INT_NAME", "INT NAME", "INTNAME",
}
_SUPERVISOR_ALIASES = {
    "SUPERVISOR", "SUPERVISOR_NAME", "SUPERVISOR NAME",
    "TEAM_LEADER", "TEAM LEADER", "FIELD_SUPERVISOR", "FIELD SUPERVISOR",
}


def _find_alias_col(upper_cols: dict, aliases: set) -> Optional[str]:
    for alias in aliases:
        if alias in upper_cols:
            return upper_cols[alias]
    return None


def _df_to_quality_records(df: pd.DataFrame, column_config: Optional[dict] = None) -> list:
    """Map any df_clean to quality_report_records-compatible dicts."""
    upper_cols = {str(c).strip().upper(): c for c in df.columns}
    std_dst = set(_COL_MAP.values())
    records = []
    overrides = {dst: src for dst, src in (column_config or {}).items() if src in df.columns}

    for _, row in df.iterrows():
        rec: dict = {}
        mapped_orig: set = set()

        for dst, src in overrides.items():
            val = row[src]
            rec[dst] = None if (isinstance(val, float) and pd.isna(val)) else val
            mapped_orig.add(src)

        for src_upper, dst in _COL_MAP.items():
            if src_upper in upper_cols and dst not in rec:
                orig = upper_cols[src_upper]
                val = row[orig]
                rec[dst] = None if (isinstance(val, float) and pd.isna(val)) else val
                mapped_orig.add(orig)

        extra = {}
        for col in df.columns:
            if col not in mapped_orig:
                val = row[col]
                if not (isinstance(val, float) and pd.isna(val)):
                    extra[str(col)] = val
        if extra:
            rec["extra_data"] = json.dumps(extra)

        records.append(rec)

    return records


@router.get("/projects")
def list_projects(user: dict = Depends(get_current_user)):
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Database not available")
    return shared_db.get_all_projects()


@router.post("/projects")
def create_project(req: CreateProjectRequest, user: dict = Depends(get_current_user)):
    if user["role"] not in _SAVE_ROLES:
        raise HTTPException(status_code=403, detail="Your role cannot create projects")
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Database not available")
    existing = shared_db.get_project_by_name(req.name.strip())
    if existing:
        raise HTTPException(status_code=409, detail=f"A project named '{req.name.strip()}' already exists")
    project_id = shared_db.create_project(req.name.strip(), user["id"])
    return shared_db.get_project(project_id)


@router.post("/projects/{project_id}/qc-results")
async def save_qc_results(
    project_id: int,
    req: SaveQCRequest,
    user: dict = Depends(get_current_user),
):
    if user["role"] not in _SAVE_ROLES:
        raise HTTPException(status_code=403, detail="Your role cannot save QC results")
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Database not available")

    project = shared_db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from job_store import file_store, job_store
    from core.loader import DataLoader
    from core.cleaner import DataCleaner

    file_path = await file_store.get(req.file_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found — it may have expired (1-hour limit)")

    loop = asyncio.get_running_loop()

    def _load_map():
        df = DataCleaner().clean(DataLoader().load(str(file_path)))
        recs = _df_to_quality_records(df, req.column_config)
        upper_cols = {str(c).strip().upper(): c for c in df.columns}

        # Build a code -> {name, supervisor} lookup for registry enrichment, if those
        # columns were identified (they aren't part of quality_report_records itself).
        # Explicit caller-supplied columns win; otherwise fall back to alias detection
        # so callers like the embedded Data tab (which never pick columns) still enrich.
        enrich: dict[str, dict] = {}
        name_col = req.interviewer_name_col or _find_alias_col(upper_cols, _INTERVIEWER_NAME_ALIASES)
        sup_col = req.interviewer_supervisor_col or _find_alias_col(upper_cols, _SUPERVISOR_ALIASES)
        if (name_col and name_col in df.columns) or (sup_col and sup_col in df.columns):
            for rec, (_, row) in zip(recs, df.iterrows()):
                code = rec.get("interviewer_id")
                if not code:
                    continue
                entry = enrich.setdefault(str(code), {})
                for col, key in ((name_col, "name"), (sup_col, "supervisor")):
                    if col and col in df.columns and key not in entry:
                        val = row[col]
                        if not (isinstance(val, float) and pd.isna(val)) and str(val).strip():
                            entry[key] = str(val).strip()
        return recs, enrich

    records, interviewer_enrichment = await loop.run_in_executor(None, _load_map)

    # Overlay QC flags from the job results so dashboard shows real flag counts
    if req.job_id:
        try:
            job = await job_store.get(req.job_id)
            if job and job.status == "complete":
                checks = (job.results or {}).get("checks", [])
                dur_flagged: set = set()
                sl_flagged: set = set()
                for check in checks:
                    cname = check.get("check_name", "")
                    for row in check.get("flagged_rows", []):
                        iid = str(
                            row.get("INSTANCE_ID") or row.get("instance_id") or
                            row.get("Instance ID") or row.get("Instance_ID") or ""
                        ).strip()
                        if not iid:
                            continue
                        if "duration" in cname:
                            dur_flagged.add(iid)
                        if "straight" in cname:
                            sl_flagged.add(iid)
                for rec in records:
                    iid = str(rec.get("instance_id") or "").strip()
                    if not iid:
                        continue
                    if rec.get("duration_flag") is None:
                        rec["duration_flag"] = "Flag" if iid in dur_flagged else "Pass"
                    if rec.get("straight_lining") is None:
                        rec["straight_lining"] = "Flag" if iid in sl_flagged else "Pass"
        except Exception:
            pass  # non-blocking — don't fail the save if job lookup fails

    upload_id = shared_db.insert_quality_records(
        project_id, user["id"], req.filename, records, req.wave_label
    )
    shared_db.lock_upload(upload_id)

    if req.column_config:
        try:
            shared_db.update_project(project_id, column_config=json.dumps(req.column_config))
        except Exception:
            pass

    # Seed/enrich the cross-project interviewer registry with every code found in this file
    codes_in_file = {str(r["interviewer_id"]) for r in records if r.get("interviewer_id")}
    known_codes = shared_db.get_interviewer_code_set()
    new_codes = codes_in_file - known_codes

    supervisor_names = {e["supervisor"] for e in interviewer_enrichment.values() if e.get("supervisor")}
    supervisor_ids = shared_db.upsert_supervisors_bulk(list(supervisor_names)) if supervisor_names else {}

    for code in codes_in_file:
        entry = interviewer_enrichment.get(code, {})
        try:
            shared_db.upsert_interviewer(
                code,
                name=entry.get("name"),
                supervisor_id=supervisor_ids.get(entry.get("supervisor")) if entry.get("supervisor") else None,
            )
        except Exception:
            pass

    return {
        "status": "ok",
        "upload_id": upload_id,
        "row_count": len(records),
        "new_interviewers": len(new_codes),
        "known_interviewers": len(known_codes & {str(r.get("interviewer_id", "")) for r in records}),
    }
