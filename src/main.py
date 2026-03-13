import asyncio
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException

from .job_runner import run_job
from .models import (
    HealthCheckResponse,
    HealthStatus,
    Job,
    JobStatus,
    JobType,
    StartJobRequest,
)

app = FastAPI(
    title="FFMPEG Service",
    description="FFMPEG service for video frame extraction and composition",
    version="0.1.0",
)

_current_job: Optional[dict[str, Any]] = None
_job_task: Optional[asyncio.Task] = None


def reset_job():
    """Reset job state. Used for testing."""
    global _current_job, _job_task
    _current_job = None
    _job_task = None


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint that returns service status."""
    return HealthCheckResponse(
        status=HealthStatus.HEALTHY,
        message="Service is running normally",
        timestamp=datetime.now().isoformat(),
    )


def _validate_job_params(job_type: JobType, input_params: dict[str, Any]) -> None:
    """
    Validate input parameters based on job type.

    Args:
        job_type: The type of job (extract or compose)
        input_params: The input parameters dictionary

    Raises:
        HTTPException: If validation fails
    """
    if job_type == JobType.EXTRACT:
        input_file = input_params.get("input_file")
        output_dir = input_params.get("output_dir")
        if not input_file or not output_dir:
            raise HTTPException(
                status_code=400,
                detail="extract job requires input_file and output_dir (paths relative to /app/data/)",
            )
    elif job_type == JobType.COMPOSE:
        input_dir = input_params.get("input_dir")
        output_file = input_params.get("output_file")
        if not input_dir or not output_file:
            raise HTTPException(
                status_code=400,
                detail="compose job requires input_dir and output_file (paths relative to /app/data/)",
            )


@app.post("/job", response_model=Job)
async def start_job(request: StartJobRequest):
    """Start a new job (extract or compose)."""
    global _current_job, _job_task

    if _current_job and _current_job["status"] == JobStatus.RUNNING:
        raise HTTPException(status_code=409, detail="A job is already running")

    if not request.job_type:
        raise HTTPException(
            status_code=400,
            detail="job_type is required (extract or compose)",
        )

    input_params = request.input_params or {}
    input_params["job_type"] = request.job_type.value

    _validate_job_params(request.job_type, input_params)

    now = datetime.now().isoformat()
    _current_job = {
        "id": request.job_id,
        "job_type": request.job_type.value,
        "status": JobStatus.RUNNING,
        "progress": 0,
        "input_params": request.input_params,
        "result": None,
        "error": None,
        "created_at": now,
        "started_at": now,
        "finished_at": None,
    }

    async def run_and_update():
        job = _current_job
        try:
            result = await run_job(
                job,
                lambda: job["status"] if job else "cancelled",
            )
            if job and job["status"] == JobStatus.RUNNING:
                job["status"] = JobStatus.COMPLETED
                job["result"] = result
                job["progress"] = 100
                job["finished_at"] = datetime.now().isoformat()
        except Exception as e:
            if job:
                job["status"] = JobStatus.FAILED
                job["error"] = str(e)
                job["finished_at"] = datetime.now().isoformat()

    _job_task = asyncio.create_task(run_and_update())
    return Job(**_current_job)


@app.get("/job", response_model=Optional[Job])
async def get_job():
    """Get the current job."""
    if _current_job is None:
        return None
    return Job(**_current_job)


@app.post("/job/cancel")
async def cancel_job():
    """Cancel the current running job."""
    global _current_job, _job_task

    if _current_job is None:
        raise HTTPException(status_code=404, detail="No job found")

    if _current_job["status"] != JobStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Job is not running")

    _current_job["status"] = JobStatus.CANCELLED
    _current_job["finished_at"] = datetime.now().isoformat()

    if _job_task and not _job_task.done():
        _job_task.cancel()

    return {"message": "Job cancelled"}
