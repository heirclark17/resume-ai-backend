"""
Simple in-memory job store for async career plan generation
"""
from typing import Dict, Any, Optional
from datetime import datetime
import uuid


class JobStore:
    """In-memory job status tracking"""

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def create_job(self, user_id: str, intake_data: Dict[str, Any]) -> str:
        """Create new job and return job_id"""
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "pending",  # pending, researching, synthesizing, completed, failed
            "progress": 0,  # 0-100
            "message": "Job queued",
            "intake": intake_data,
            "research_data": None,
            "plan": None,
            "plan_id": None,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **kwargs):
        """Update job status"""
        if job_id in self._jobs:
            self._jobs[job_id].update(kwargs)
            self._jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

    def delete_job(self, job_id: str):
        """Remove completed job after retrieval"""
        if job_id in self._jobs:
            del self._jobs[job_id]

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs older than max_age_hours"""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        to_delete = []
        for job_id, job in self._jobs.items():
            created = datetime.fromisoformat(job["created_at"])
            if created < cutoff:
                to_delete.append(job_id)

        for job_id in to_delete:
            del self._jobs[job_id]


# Global job store instance
job_store = JobStore()
