import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from core.loader import DataLoader
from job_store import file_store
from schemas import EDARequest

router = APIRouter()


# ── Chart computation helpers ──────────────────────────────────────────────────

def _to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _bar_line(
    df: pd.DataFrame,
    x_col: str,
    y_cols: List[str],
    agg_func: str,
    chart_type: str,
    color_col: Optional[str],
) -> Dict[str, Any]:
    if x_col not in df.columns:
        raise ValueError(f"Column '{x_col}' not found")

    valid_y = [c for c in y_cols if c in df.columns]
    if not valid_y:
        raise ValueError("No valid y columns found in dataset")

    agg_map = {"mean": "mean", "sum": "sum", "count": "count", "min": "min", "max": "max"}
    agg = agg_map.get(agg_func, "mean")

    group_cols = [x_col]
    if color_col and color_col in df.columns:
        group_cols.append(color_col)

    grouped = df.groupby(group_cols)[valid_y].agg(agg).reset_index()
    # Rename x_col to "name" for Recharts compatibility
    grouped = grouped.rename(columns={x_col: "name"})

    return {
        "chart_type": chart_type,
        "data": _to_records(grouped),
        "metadata": {"x_col": x_col, "y_cols": valid_y, "agg_func": agg_func},
    }


def _scatter(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: Optional[str],
) -> Dict[str, Any]:
    if x_col not in df.columns:
        raise ValueError(f"Column '{x_col}' not found")
    if y_col not in df.columns:
        raise ValueError(f"Column '{y_col}' not found")

    cols = [x_col, y_col]
    if color_col and color_col in df.columns:
        cols.append(color_col)

    subset = df[cols].dropna().rename(columns={x_col: "x", y_col: "y"})

    return {
        "chart_type": "scatter",
        "data": _to_records(subset),
        "metadata": {"x_col": x_col, "y_col": y_col, "color_col": color_col},
    }


def _histogram(df: pd.DataFrame, x_col: str) -> Dict[str, Any]:
    if x_col not in df.columns:
        raise ValueError(f"Column '{x_col}' not found")

    col = df[x_col].dropna()

    if pd.api.types.is_numeric_dtype(col):
        counts, bin_edges = np.histogram(col, bins="auto")
        data = [
            {"bin": f"{bin_edges[i]:.4g}–{bin_edges[i + 1]:.4g}", "count": int(counts[i])}
            for i in range(len(counts))
        ]
    else:
        vc = col.value_counts()
        data = [{"bin": str(k), "count": int(v)} for k, v in vc.items()]

    return {
        "chart_type": "histogram",
        "data": data,
        "metadata": {"x_col": x_col},
    }


def _heatmap(df: pd.DataFrame, cols: List[str]) -> Dict[str, Any]:
    valid = [c for c in cols if c in df.columns]
    numeric = df[valid].select_dtypes(include="number") if valid else df.select_dtypes(include="number")

    if numeric.shape[1] < 2:
        raise ValueError("Need at least 2 numeric columns for a heatmap")

    corr = numeric.corr().round(4)
    matrix = [[None if np.isnan(v) else round(float(v), 4) for v in row] for row in corr.values]

    return {
        "chart_type": "heatmap",
        "data": {"columns": corr.columns.tolist(), "matrix": matrix},
        "metadata": {"columns": corr.columns.tolist()},
    }


def _box_stats(vals: pd.Series) -> Dict[str, Any]:
    q1, median, q3 = float(vals.quantile(0.25)), float(vals.quantile(0.5)), float(vals.quantile(0.75))
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return {
        "min": float(vals.min()),
        "q1": q1,
        "median": median,
        "q3": q3,
        "max": float(vals.max()),
        "outliers": [float(v) for v in vals[(vals < lower) | (vals > upper)]],
    }


def _box(
    df: pd.DataFrame,
    x_col: str,
    y_cols: List[str],
    color_col: Optional[str],
) -> Dict[str, Any]:
    valid_y = [
        c for c in y_cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
    ]
    if not valid_y:
        raise ValueError("No valid numeric y columns for box plot")

    data: List[Dict[str, Any]] = []

    if x_col and x_col in df.columns:
        for group_val in df[x_col].dropna().unique():
            mask = df[x_col] == group_val
            entry: Dict[str, Any] = {"name": str(group_val)}
            for y in valid_y:
                vals = df.loc[mask, y].dropna()
                if len(vals) > 0:
                    entry[y] = _box_stats(vals)
            data.append(entry)
    else:
        for y in valid_y:
            vals = df[y].dropna()
            if len(vals) > 0:
                data.append({"name": y, **_box_stats(vals)})

    return {
        "chart_type": "box",
        "data": data,
        "metadata": {"x_col": x_col, "y_cols": valid_y},
    }


def _compute_eda(file_path: Path, req: EDARequest) -> Dict[str, Any]:
    loader = DataLoader()
    df = loader.load(str(file_path))

    chart_type = req.chart_type
    x_col = req.x_col
    y_cols = req.y_cols or []
    color_col = req.color_col
    agg_func = req.agg_func

    if chart_type == "histogram":
        return _histogram(df, x_col)
    if chart_type == "heatmap":
        return _heatmap(df, y_cols)
    if chart_type == "scatter":
        y_col = y_cols[0] if y_cols else x_col
        return _scatter(df, x_col, y_col, color_col)
    if chart_type == "box":
        return _box(df, x_col, y_cols, color_col)
    # bar or line
    return _bar_line(df, x_col, y_cols, agg_func, chart_type, color_col)


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/eda")
async def eda(req: EDARequest):
    file_path = await file_store.get(req.file_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail={"error": "file_id not found or file has expired"})

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _compute_eda, file_path, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    return result


# ── Summary stats ──────────────────────────────────────────────────────────────

def _compute_summary(file_path: Path) -> Dict[str, Any]:
    loader = DataLoader()
    df = loader.load(str(file_path))

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    numeric_summary = []
    for col in numeric_cols:
        s = df[col].dropna()
        if len(s) > 0:
            numeric_summary.append({
                "column": col,
                "count": int(s.count()),
                "mean": round(float(s.mean()), 4),
                "std": round(float(s.std()), 4),
                "min": round(float(s.min()), 4),
                "p25": round(float(s.quantile(0.25)), 4),
                "median": round(float(s.median()), 4),
                "p75": round(float(s.quantile(0.75)), 4),
                "max": round(float(s.max()), 4),
            })

    missing_summary = []
    for col in df.columns:
        n_missing = int(df[col].isnull().sum())
        if n_missing > 0:
            missing_summary.append({
                "column": col,
                "missing_count": n_missing,
                "missing_pct": round(n_missing / len(df) * 100, 2),
            })

    cat_summary = []
    for col in df.select_dtypes(include="object").columns[:20]:
        vc = df[col].value_counts().head(10)
        cat_summary.append({
            "column": col,
            "unique_count": int(df[col].nunique()),
            "top_values": [{"value": str(k), "count": int(v)} for k, v in vc.items()],
        })

    return {
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "numeric_summary": numeric_summary,
        "missing_summary": missing_summary,
        "categorical_summary": cat_summary,
    }


@router.get("/eda/summary/{file_id}")
async def eda_summary(file_id: str):
    file_path = await file_store.get(file_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail={"error": "file_id not found or expired"})

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _compute_summary, file_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    return result
