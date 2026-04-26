import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from job_store import REPORTS_DIR, UPLOAD_DIR
from routers import ai, compare, eda, interviewers, qc

logger = logging.getLogger(__name__)

FILE_MAX_AGE = 3600   # seconds before temp files are removed
CLEANUP_INTERVAL = 3600  # how often the cleanup loop runs


async def _cleanup_loop() -> None:
    """Remove uploaded files and generated reports older than FILE_MAX_AGE."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        now = time.time()
        for directory in (UPLOAD_DIR, REPORTS_DIR):
            try:
                for path in directory.rglob("*"):
                    if path.is_file() and (now - path.stat().st_mtime) > FILE_MAX_AGE:
                        path.unlink(missing_ok=True)
                        logger.info("Cleaned up expired file: %s", path)
            except Exception:
                logger.exception("Error during temp-file cleanup in %s", directory)


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.create_task(_cleanup_loop())
    yield


app = FastAPI(
    title="Servallab QC API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(qc.router, prefix="/api")
app.include_router(eda.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(interviewers.router, prefix="/api")
app.include_router(compare.router, prefix="/api")


@app.get("/health")
async def health():
    try:
        version = json.loads(Path("assets/app_version.json").read_text())["version"]
    except Exception:
        version = "unknown"
    return {"status": "ok", "version": version}
