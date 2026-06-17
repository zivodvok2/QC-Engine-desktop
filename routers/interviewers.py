"""
routers/interviewers.py — Interviewer risk scoring from QC results
"""

import asyncio
import json
from collections import Counter
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.cleaner import DataCleaner
from core.loader import DataLoader
from job_store import file_store, job_store

router = APIRouter()

WEIGHTS = {"fabrication": 0.40, "duration": 0.25, "straightlining": 0.25, "productivity": 0.10}

FLAG_MAPPINGS = [
    ("interviewer_duration_check",     "duration_flags"),
    ("straightlining_check",           "straightlining_flags"),
    ("fabrication_check",              "fabrication_flags"),
    ("interviewer_productivity_check", "productivity_flags"),
    ("verbatim_quality_check",         "verbatim_flags"),
]


class RiskRequest(BaseModel):
    file_id: str
    job_id: str
    interviewer_column: str
    red_threshold: int = 60
    amber_threshold: int = 30
    supervisor_column: Optional[str] = None
    date_column: Optional[str] = None


def _build_risk_table(
    df: pd.DataFrame,
    checks: List[Dict[str, Any]],
    interviewer_col: str,
    red_thr: int,
    amber_thr: int,
    supervisor_col: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if interviewer_col not in df.columns:
        raise ValueError(f"Column '{interviewer_col}' not found in dataset")

    total_by_int = df.groupby(interviewer_col).size().rename("total_interviews")
    scores = pd.DataFrame(index=total_by_int.index)
    scores.index.name = interviewer_col
    scores = scores.join(total_by_int)

    flag_cols = ["fabrication_flags", "duration_flags", "straightlining_flags",
                 "productivity_flags", "verbatim_flags"]
    for col in flag_cols:
        scores[col] = 0

    for check_name, flag_col in FLAG_MAPPINGS:
        check_data = next((c for c in checks if c["check_name"] == check_name), None)
        if check_data and check_data["flag_count"] > 0:
            flagged_rows = check_data.get("flagged_rows", [])
            if flagged_rows and interviewer_col in (flagged_rows[0] if flagged_rows else {}):
                counts: Dict[str, int] = {}
                for row in flagged_rows:
                    key = str(row.get(interviewer_col, ""))
                    if key:
                        counts[key] = counts.get(key, 0) + 1
                for idx in scores.index:
                    scores.loc[idx, flag_col] = int(counts.get(str(idx), 0))

    for base in ["fabrication", "duration", "straightlining", "productivity", "verbatim"]:
        scores[f"{base}_rate"] = (
            scores[f"{base}_flags"] / scores["total_interviews"].clip(lower=1)
        ).clip(0, 1)

    scores["risk_score"] = (
        scores["fabrication_rate"]    * WEIGHTS["fabrication"]    +
        scores["duration_rate"]       * WEIGHTS["duration"]       +
        scores["straightlining_rate"] * WEIGHTS["straightlining"] +
        scores["productivity_rate"]   * WEIGHTS["productivity"]
    ).mul(100).round(1)

    scores["risk_level"] = scores["risk_score"].apply(
        lambda s: "HIGH" if s >= red_thr else ("MEDIUM" if s >= amber_thr else "LOW")
    )
    scores["total_flags"] = scores[flag_cols].sum(axis=1)
    scores["flag_rate_pct"] = (
        scores["total_flags"] / scores["total_interviews"].clip(lower=1) * 100
    ).round(1)

    # Attach supervisor — most frequent supervisor value for each interviewer
    if supervisor_col and supervisor_col in df.columns:
        sup_map = (
            df.groupby(interviewer_col)[supervisor_col]
            .agg(lambda x: x.mode().iloc[0] if len(x) > 0 else None)
        )
        scores["supervisor"] = scores.index.map(sup_map).astype(str)
    else:
        scores["supervisor"] = None

    result_df = scores.reset_index().sort_values("risk_score", ascending=False)
    return json.loads(result_df.to_json(orient="records", date_format="iso"))


def _compute_date_trends(
    checks: List[Dict[str, Any]],
    date_col: str,
) -> List[Dict[str, Any]]:
    """Count total flags per date across all checks."""
    dates: List[str] = []
    for check in checks:
        for row in check.get("flagged_rows", []):
            val = row.get(date_col)
            if val is not None:
                dates.append(str(val)[:10])
    counts = Counter(dates)
    return [{"date": d, "flag_count": c} for d, c in sorted(counts.items())]


@router.post("/interviewers/risk")
async def interviewer_risk(req: RiskRequest):
    file_path = await file_store.get(req.file_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail={"error": "file_id not found"})

    job = await job_store.get(req.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_id not found"})
    if job.status != "complete":
        raise HTTPException(
            status_code=409,
            detail={"error": f"Job not complete yet (status: {job.status})"},
        )

    checks = (job.results or {}).get("checks", [])

    def _compute(path, checks, int_col, red_thr, amber_thr, sup_col):
        loader = DataLoader()
        cleaner = DataCleaner()
        df = cleaner.clean(loader.load(str(path)))
        return _build_risk_table(df, checks, int_col, red_thr, amber_thr, sup_col)

    try:
        loop = asyncio.get_running_loop()
        rows = await loop.run_in_executor(
            None, _compute, file_path, checks, req.interviewer_column,
            req.red_threshold, req.amber_threshold, req.supervisor_column,
        )
        trends = _compute_date_trends(checks, req.date_column) if req.date_column else []
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    return {
        "rows": rows,
        "interviewer_column": req.interviewer_column,
        "date_trends": trends,
    }
