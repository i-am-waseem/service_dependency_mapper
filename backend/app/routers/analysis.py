import uuid
import structlog
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.models.graph import AnalysisJob, JobStatus
from app.agents import planner
from app.services import graph_service

router = APIRouter(prefix="/api/analysis", tags=["analysis"])
logger = structlog.get_logger(__name__)

# In-memory job store — sufficient for a demo; replace with Redis for production
_jobs: dict[str, AnalysisJob] = {}


def reset_jobs() -> None:
    """Clear all jobs. Used in tests to ensure isolation between test cases."""
    _jobs.clear()


@router.post("/run", summary="Trigger AI agent analysis (returns job_id for polling)")
async def run_analysis(background_tasks: BackgroundTasks):
    if not graph_service.is_loaded():
        raise HTTPException(status_code=400, detail="No graph loaded. POST /api/services/load first.")

    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _jobs[job_id] = job
    background_tasks.add_task(_execute_analysis, job_id)
    logger.info("analysis_job_queued", job_id=job_id)
    return {"job_id": job_id, "status": job.status}


@router.get("/{job_id}", response_model=AnalysisJob, summary="Poll analysis job status / result")
async def get_analysis(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@router.get("", summary="List all analysis jobs")
async def list_jobs() -> list[AnalysisJob]:
    return list(_jobs.values())


async def _execute_analysis(job_id: str) -> None:
    job = _jobs[job_id]
    _jobs[job_id] = job.model_copy(update={"status": JobStatus.RUNNING})
    try:
        result = await planner.run_analysis()
        _jobs[job_id] = job.model_copy(update={
            "status": JobStatus.COMPLETED,
            "result": result,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("analysis_job_completed", job_id=job_id)
    except Exception as exc:
        logger.error("analysis_job_failed", job_id=job_id, error=str(exc))
        _jobs[job_id] = job.model_copy(update={
            "status": JobStatus.FAILED,
            "error": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
