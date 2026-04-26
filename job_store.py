import asyncio
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(Path(tempfile.gettempdir()) / "servallab_uploads")))
REPORTS_DIR = Path(os.environ.get("REPORTS_DIR", str(Path(tempfile.gettempdir()) / "servallab_reports")))


@dataclass
class JobState:
    job_id: str
    file_id: str
    status: str = "queued"  # queued | running | complete | failed
    progress: int = 0
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    report_path: Optional[str] = None


class FileStore:
    """Thread-safe in-memory map of file_id -> Path."""

    def __init__(self):
        self._files: Dict[str, Path] = {}
        self._lock = asyncio.Lock()

    async def put(self, file_id: str, path: Path) -> None:
        async with self._lock:
            self._files[file_id] = path

    async def get(self, file_id: str) -> Optional[Path]:
        async with self._lock:
            return self._files.get(file_id)

    async def delete(self, file_id: str) -> None:
        async with self._lock:
            self._files.pop(file_id, None)


class JobStore:
    """Thread-safe in-memory map of job_id -> JobState."""

    def __init__(self):
        self._jobs: Dict[str, JobState] = {}
        self._lock = asyncio.Lock()

    async def create(self, job_id: str, file_id: str) -> JobState:
        async with self._lock:
            job = JobState(job_id=job_id, file_id=file_id)
            self._jobs[job_id] = job
            return job

    async def get(self, job_id: str) -> Optional[JobState]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job_id: str, **kwargs) -> Optional[JobState]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, value in kwargs.items():
                setattr(job, key, value)
            return job

    async def delete(self, job_id: str) -> None:
        async with self._lock:
            self._jobs.pop(job_id, None)


file_store = FileStore()
job_store = JobStore()
