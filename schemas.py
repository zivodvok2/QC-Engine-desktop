from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    rows: int
    columns: int
    column_names: List[str]


class RunRequest(BaseModel):
    file_id: str
    config: Dict[str, Any]


class RunResponse(BaseModel):
    job_id: str
    status: str = "queued"


class StatusResponse(BaseModel):
    job_id: str
    status: str  # queued | running | complete | failed
    progress: int
    error: Optional[str] = None


class CheckResultJSON(BaseModel):
    check_name: str
    issue_type: str
    severity: str
    flag_count: int
    flagged_rows: List[Dict[str, Any]]


class ResultsResponse(BaseModel):
    job_id: str
    total_flags: int
    flagged_by_severity: Dict[str, int]
    checks: List[CheckResultJSON]


class EDARequest(BaseModel):
    file_id: str
    x_col: str
    y_cols: List[str] = []
    color_col: Optional[str] = None
    chart_type: str  # bar | line | scatter | histogram | heatmap | box
    agg_func: str = "mean"  # mean | sum | count | min | max


class LogicValidateRequest(BaseModel):
    file_id: str
    rules: List[Dict[str, Any]]


class LogicValidateResponse(BaseModel):
    violation_count: int
    flagged_rows: List[Dict[str, Any]]


class ColumnsResponse(BaseModel):
    columns: List[str]
    dtypes: Dict[str, str]
    sample: List[Dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    version: str
