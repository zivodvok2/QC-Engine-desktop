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


def _df_to_quality_records(df: pd.DataFrame) -> list:
    """Map any df_clean to quality_report_records-compatible dicts."""
    upper_cols = {str(c).strip().upper(): c for c in df.columns}
    std_dst = set(_COL_MAP.values())
    records = []

    for _, row in df.iterrows():
        rec: dict = {}
        mapped_orig: set = set()

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
        return existing
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

    from job_store import file_store
    from core.loader import DataLoader
    from core.cleaner import DataCleaner

    file_path = await file_store.get(req.file_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found — it may have expired (1-hour limit)")

    loop = asyncio.get_running_loop()

    def _load_map():
        df = DataCleaner().clean(DataLoader().load(str(file_path)))
        return _df_to_quality_records(df)

    records = await loop.run_in_executor(None, _load_map)

    upload_id = shared_db.insert_quality_records(
        project_id, user["id"], req.filename, records, req.wave_label
    )

    # Seed interviewer registry with any new codes found in this file
    known_codes = shared_db.get_interviewer_code_set()
    new_codes = {
        str(r["interviewer_id"]) for r in records
        if r.get("interviewer_id") and str(r["interviewer_id"]) not in known_codes
    }
    for code in new_codes:
        try:
            shared_db.upsert_interviewer(code)
        except Exception:
            pass

    return {
        "status": "ok",
        "upload_id": upload_id,
        "row_count": len(records),
        "new_interviewers": len(new_codes),
        "known_interviewers": len(known_codes & {str(r.get("interviewer_id", "")) for r in records}),
    }
