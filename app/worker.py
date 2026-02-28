"""
Background job worker — polls async_jobs table and dispatches to handlers.

Can run as:
  1. FastAPI background task (same process, via startup event)
  2. Standalone worker (separate Railway service): python -m app.worker

Handles:
  - career_plan: Perplexity research + OpenAI synthesis
  - tailor_resume: Company research + resume tailoring + DOCX generation
  - cover_letter: Cover letter generation
"""
import asyncio
from typing import Callable, Coroutine, Dict

from app.database import AsyncSessionLocal
from app.services import job_manager
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Job handler registry
# ---------------------------------------------------------------------------
_handlers: Dict[str, Callable] = {}


def register_handler(job_type: str, handler: Callable) -> None:
    """Register an async handler for a job type."""
    _handlers[job_type] = handler


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------

async def worker_loop(poll_interval: float = 2.0, max_idle_interval: float = 10.0) -> None:
    """
    Poll for pending jobs and dispatch to registered handlers.

    Uses adaptive polling: starts at poll_interval, backs off to max_idle_interval
    when no jobs are found, resets on job found.
    """
    current_interval = poll_interval
    logger.info("worker.started", extra={"poll_interval": poll_interval})

    while True:
        try:
            async with AsyncSessionLocal() as db:
                job = await job_manager.claim_next_job(db)

                if job:
                    current_interval = poll_interval  # Reset to fast polling
                    handler = _handlers.get(job.job_type)

                    if handler:
                        try:
                            await handler(db, job)
                        except Exception as exc:
                            logger.error(
                                "worker.handler_error",
                                extra={
                                    "job_id": job.id,
                                    "job_type": job.job_type,
                                    "error": str(exc)[:500],
                                },
                            )
                            await job_manager.fail_job(db, job.id, str(exc)[:1000])
                    else:
                        logger.warning(
                            "worker.no_handler",
                            extra={"job_type": job.job_type, "job_id": job.id},
                        )
                        await job_manager.fail_job(
                            db, job.id, f"No handler registered for job type: {job.job_type}"
                        )
                else:
                    # No jobs found — back off
                    current_interval = min(current_interval * 1.5, max_idle_interval)

        except Exception as exc:
            logger.error("worker.poll_error", extra={"error": str(exc)[:500]})
            current_interval = max_idle_interval

        await asyncio.sleep(current_interval)


async def run_cleanup(interval_hours: int = 6) -> None:
    """Periodically clean up old completed/failed jobs."""
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            async with AsyncSessionLocal() as db:
                deleted = await job_manager.cleanup_old_jobs(db, max_age_hours=72)
                if deleted:
                    logger.info("worker.cleanup", extra={"deleted": deleted})
        except Exception as exc:
            logger.error("worker.cleanup_error", extra={"error": str(exc)[:200]})


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """Run worker as standalone process."""
    from app.database import init_db
    await init_db()

    # Register all handlers
    _register_default_handlers()

    # Run worker + cleanup concurrently
    await asyncio.gather(
        worker_loop(),
        run_cleanup(),
    )


def _register_default_handlers() -> None:
    """Register built-in job type handlers."""
    # Import handlers lazily to avoid circular imports
    from app.routes.tailoring import _process_tailor_job
    from app.routes.cover_letters import _process_cover_letter_job
    from app.routes.interview_prep import _process_interview_prep_job

    async def handle_tailor(db, job):
        from app.routes.tailoring import TailorRequest
        import json
        data = json.loads(job.input_data) if isinstance(job.input_data, str) else job.input_data
        request = TailorRequest(**data.get("request", data))
        await _process_tailor_job(str(job.id), request, job.user_id)

    async def handle_cover_letter(db, job):
        from app.routes.cover_letters import GenerateRequest
        import json
        data = json.loads(job.input_data) if isinstance(job.input_data, str) else job.input_data
        request = GenerateRequest(**data.get("request", data))
        await _process_cover_letter_job(str(job.id), request, job.user_id)

    async def handle_interview_prep(db, job):
        import json
        data = json.loads(job.input_data) if isinstance(job.input_data, str) else job.input_data
        tailored_resume_id = data.get("tailored_resume_id")
        await _process_interview_prep_job(str(job.id), tailored_resume_id)

    async def handle_career_plan(db, job):
        """Career plan jobs are processed inline by career_path.py — mark complete."""
        logger.info("worker.career_plan_skip", extra={"job_id": str(job.id),
            "note": "Career plan jobs use inline processing in career_path.py"})

    register_handler("tailor_resume", handle_tailor)
    register_handler("cover_letter", handle_cover_letter)
    register_handler("interview_prep", handle_interview_prep)
    register_handler("career_plan", handle_career_plan)


if __name__ == "__main__":
    asyncio.run(main())
