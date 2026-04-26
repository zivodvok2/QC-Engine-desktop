"""
routers/compare.py — Wave comparison: diff two survey datasets
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import List

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from core.loader import DataLoader
from job_store import UPLOAD_DIR, file_store

router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


class DiffRequest(BaseModel):
    file_id_1: str
    file_id_2: str
    id_column: str
    compare_columns: List[str] = []


@router.post("/compare/upload")
async def compare_upload(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"},
        )

    file_id = str(uuid.uuid4())
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

    return {
        "file_id": file_id,
        "filename": file.filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": df.columns.tolist(),
    }


def _compute_diff(
    path1: Path,
    path2: Path,
    id_col: str,
    compare_cols: List[str],
):
    loader = DataLoader()
    df1 = loader.load(str(path1))
    df2 = loader.load(str(path2))

    if id_col not in df1.columns:
        raise ValueError(f"ID column '{id_col}' not found in wave 1")
    if id_col not in df2.columns:
        raise ValueError(f"ID column '{id_col}' not found in wave 2")

    ids1 = set(df1[id_col].dropna().astype(str))
    ids2 = set(df2[id_col].dropna().astype(str))
    new_ids = ids2 - ids1
    removed_ids = ids1 - ids2
    common_ids = ids1 & ids2

    new_rows = json.loads(
        df2[df2[id_col].astype(str).isin(new_ids)].head(500)
        .to_json(orient="records", date_format="iso")
    )
    removed_rows = json.loads(
        df1[df1[id_col].astype(str).isin(removed_ids)].head(500)
        .to_json(orient="records", date_format="iso")
    )

    changed_rows: list = []
    if compare_cols and common_ids:
        valid_cols = [c for c in compare_cols if c in df1.columns and c in df2.columns]
        if valid_cols:
            w1 = df1[df1[id_col].astype(str).isin(common_ids)].set_index(id_col)[valid_cols]
            w2 = df2[df2[id_col].astype(str).isin(common_ids)].set_index(id_col)[valid_cols]
            w1.index = w1.index.astype(str)
            w2.index = w2.index.astype(str)
            common_idx = w1.index.intersection(w2.index)
            w1 = w1.loc[common_idx]
            w2 = w2.loc[common_idx]
            diff_mask = w1.astype(str) != w2.astype(str)
            changed_index = diff_mask.any(axis=1)
            for rid in changed_index[changed_index].index[:500]:
                entry: dict = {id_col: rid}
                for col in valid_cols:
                    v1, v2 = str(w1.at[rid, col]), str(w2.at[rid, col])
                    if v1 != v2:
                        entry[f"{col}_wave1"] = w1.at[rid, col]
                        entry[f"{col}_wave2"] = w2.at[rid, col]
                changed_rows.append(entry)

    # Interviewer shift data — all common columns for the calling component
    common_columns = [c for c in df1.columns if c in df2.columns]

    return {
        "summary": {
            "wave1_rows": len(df1),
            "wave2_rows": len(df2),
            "new_count": len(new_ids),
            "removed_count": len(removed_ids),
            "common_count": len(common_ids),
            "changed_count": len(changed_rows),
        },
        "new_rows": new_rows,
        "removed_rows": removed_rows,
        "changed_rows": changed_rows,
        "common_columns": common_columns,
        # Pre-computed interviewer shift data is done client-side by selecting a column
        # but we send per-interviewer counts for both waves so client can join them
        "wave1_col_counts": {},  # filled lazily via /compare/interviewer-shift
        "wave2_col_counts": {},
    }


@router.post("/compare/diff")
async def compare_diff(req: DiffRequest):
    path1 = await file_store.get(req.file_id_1)
    path2 = await file_store.get(req.file_id_2)

    if path1 is None or not path1.exists():
        raise HTTPException(status_code=404, detail={"error": "file_id_1 not found or expired"})
    if path2 is None or not path2.exists():
        raise HTTPException(status_code=404, detail={"error": "file_id_2 not found or expired"})

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _compute_diff, path1, path2, req.id_column, req.compare_columns
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    return result


class InterviewerShiftRequest(BaseModel):
    file_id_1: str
    file_id_2: str
    interviewer_column: str


@router.post("/compare/interviewer-shift")
async def interviewer_shift(req: InterviewerShiftRequest):
    path1 = await file_store.get(req.file_id_1)
    path2 = await file_store.get(req.file_id_2)

    if path1 is None or not path1.exists():
        raise HTTPException(status_code=404, detail={"error": "file_id_1 not found"})
    if path2 is None or not path2.exists():
        raise HTTPException(status_code=404, detail={"error": "file_id_2 not found"})

    def _compute(p1, p2, col):
        loader = DataLoader()
        df1 = loader.load(str(p1))
        df2 = loader.load(str(p2))
        if col not in df1.columns or col not in df2.columns:
            raise ValueError(f"Column '{col}' not found in both files")
        s1 = df1[col].value_counts().rename("wave1_count")
        s2 = df2[col].value_counts().rename("wave2_count")
        comp = pd.concat([s1, s2], axis=1).fillna(0).astype(int)
        comp["change"] = comp["wave2_count"] - comp["wave1_count"]
        comp["change_pct"] = (
            (comp["change"] / comp["wave1_count"].replace(0, 1)) * 100
        ).round(1)
        comp = comp.reset_index().rename(columns={"index": col})
        comp = comp.sort_values("change", ascending=False)
        return json.loads(comp.to_json(orient="records"))

    try:
        loop = asyncio.get_running_loop()
        rows = await loop.run_in_executor(None, _compute, path1, path2, req.interviewer_column)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    return {"rows": rows, "interviewer_column": req.interviewer_column}
