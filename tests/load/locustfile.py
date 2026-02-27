"""
Load test script for ResumeAI backend.

Simulates a realistic user flow:
  1. Health check
  2. List resumes
  3. Submit async tailoring job
  4. Poll for result
  5. Generate cover letter (async)
  6. Poll for result

Run:
    pip install locust
    locust -f tests/load/locustfile.py --host https://YOUR-RAILWAY-URL

Then open http://localhost:8089 to configure users/spawn rate and start.
"""

import os
import time
import json
from locust import HttpUser, task, between, SequentialTaskSet


# ---------------------------------------------------------------------------
# Configuration — override with env vars for different environments
# ---------------------------------------------------------------------------
AUTH_TOKEN = os.getenv("LOAD_TEST_TOKEN", "")          # Supabase JWT
USER_ID = os.getenv("LOAD_TEST_USER_ID", "load-test")  # X-User-ID fallback
BASE_RESUME_ID = int(os.getenv("LOAD_TEST_RESUME_ID", "1"))


def auth_headers():
    headers = {"X-User-ID": USER_ID, "X-Correlation-ID": f"load-test-{time.monotonic()}"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    return headers


# ---------------------------------------------------------------------------
# Sequential flow: tailor → poll
# ---------------------------------------------------------------------------
class TailorFlow(SequentialTaskSet):
    """Simulate a user tailoring a resume and polling for the result."""

    job_id = None

    @task
    def submit_tailor(self):
        payload = {
            "base_resume_id": BASE_RESUME_ID,
            "company": "Test Corp",
            "job_title": "Senior Security Program Manager",
            "job_description": (
                "We are seeking an experienced Security Program Manager to lead "
                "cross-functional initiatives. Requires 8+ years experience with "
                "NIST, ISO 27001, and stakeholder management."
            ),
        }
        with self.client.post(
            "/api/tailor/tailor-async",
            json=payload,
            headers=auth_headers(),
            name="/api/tailor/tailor-async",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self.job_id = data.get("job_id")
                if not self.job_id:
                    resp.failure("No job_id in response")
            else:
                resp.failure(f"Submit failed: {resp.status_code}")

    @task
    def poll_tailor(self):
        if not self.job_id:
            return

        max_polls = 60  # 2 minutes at 2s intervals
        for _ in range(max_polls):
            with self.client.get(
                f"/api/tailor/job/{self.job_id}",
                headers=auth_headers(),
                name="/api/tailor/job/[id]",
                catch_response=True,
            ) as resp:
                if resp.status_code != 200:
                    resp.failure(f"Poll error: {resp.status_code}")
                    return

                data = resp.json()
                status = data.get("status")

                if status == "completed":
                    resp.success()
                    return
                elif status == "failed":
                    resp.failure(f"Job failed: {data.get('error', 'unknown')}")
                    return

            time.sleep(2)

        # Timeout
        self.client.get(
            f"/api/tailor/job/{self.job_id}",
            headers=auth_headers(),
            name="/api/tailor/job/[id] (timeout)",
        )

    @task
    def stop(self):
        self.interrupt()


# ---------------------------------------------------------------------------
# User class
# ---------------------------------------------------------------------------
class ResumeAIUser(HttpUser):
    """Simulates a typical user session."""

    wait_time = between(1, 3)

    @task(3)
    def health_check(self):
        """Lightweight probe — should always be fast."""
        self.client.get("/health", name="/health")

    @task(2)
    def deep_health(self):
        """Deep health check — verifies DB + queue."""
        self.client.get("/health/ready", name="/health/ready")

    @task(1)
    def list_resumes(self):
        """List user's resumes."""
        self.client.get(
            "/api/resumes/list",
            headers=auth_headers(),
            name="/api/resumes/list",
        )

    @task(1)
    def metrics(self):
        """Fetch in-process metrics."""
        self.client.get("/metrics", name="/metrics")

    tasks = {TailorFlow: 1}
