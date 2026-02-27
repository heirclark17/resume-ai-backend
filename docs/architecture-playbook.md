# Scalable Backend & AI Architecture Playbook

> Resume AI App — Production Architecture Reference
> Last updated: 2026-02-27

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Backend Design Principles](#2-backend-design-principles)
3. [External Service Gateway](#3-external-service-gateway)
4. [Client/UX Async Patterns](#4-clientux-async-patterns)
5. [Concrete Code Examples](#5-concrete-code-examples)
6. [Monitoring & Load Testing](#6-monitoring--load-testing)
7. [Prioritization & Evolution Path](#7-prioritization--evolution-path)

---

## 1. Architecture Overview

### System Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ React Native │  │  React Web   │  │  API Direct  │                 │
│  │   (iOS/And)  │  │  (Vercel)    │  │  (curl/test) │                 │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                 │
└─────────┼──────────────────┼──────────────────┼─────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     RAILWAY PLATFORM                                    │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    API SERVICE (FastAPI)                           │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │  │
│  │  │  CORS    │ │   WAF    │ │ Rate     │ │ Correlation ID       │ │  │
│  │  │Middleware│ │Middleware│ │ Limiter  │ │ Middleware            │ │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────────┬───────────┘ │  │
│  │       ▼            ▼            ▼                   ▼             │  │
│  │  ┌────────────────────────────────────────────────────────────┐   │  │
│  │  │              ROUTE HANDLERS (stateless)                    │   │  │
│  │  │  /api/tailor  /api/interview-prep  /api/cover-letters     │   │  │
│  │  │  /api/career-path  /api/resumes  /api/jobs  /api/auth     │   │  │
│  │  └───────────────────────┬────────────────────────────────────┘   │  │
│  │                          │                                        │  │
│  │  ┌───────────────────────▼────────────────────────────────────┐   │  │
│  │  │              SERVICE GATEWAY                                │   │  │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌───────────────────┐   │   │  │
│  │  │  │Circuit Breaker│ │  Semaphore   │ │ Retry + Backoff   │   │   │  │
│  │  │  │  per service  │ │  per service │ │ per service        │   │   │  │
│  │  │  └──────────────┘ └──────────────┘ └───────────────────┘   │   │  │
│  │  └───────────────────────┬────────────────────────────────────┘   │  │
│  │                          │                                        │  │
│  │  ┌───────────────────────▼────────────────────────────────────┐   │  │
│  │  │              JOB MANAGER                                    │   │  │
│  │  │  enqueue_job() → PostgreSQL async_jobs table                │   │  │
│  │  │  claim_next_job() → Worker picks up                         │   │  │
│  │  │  update_progress() → Client polls for status                │   │  │
│  │  └───────────────────────┬────────────────────────────────────┘   │  │
│  └──────────────────────────┼────────────────────────────────────────┘  │
│                             │                                           │
│  ┌──────────────────────────▼────────────────────────────────────────┐  │
│  │                    POSTGRESQL (Railway)                            │  │
│  │  ┌──────────┐ ┌───────────┐ ┌────────────┐ ┌──────────────────┐  │  │
│  │  │  users   │ │  resumes  │ │ async_jobs  │ │ tailored_resumes │  │  │
│  │  │  jobs    │ │ companies │ │ (job queue) │ │ interview_preps  │  │  │
│  │  └──────────┘ └───────────┘ └────────────┘ └──────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
          │                  │                  │                  │
          ▼                  ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   OpenAI     │  │  Perplexity  │  │  Firecrawl   │  │  Playwright  │
│  GPT-4.1-mini│  │   Sonar      │  │  Job Extract │  │  Fallback    │
│  max_conc=10 │  │  max_conc=5  │  │  max_conc=3  │  │  max_conc=2  │
│  timeout=90s │  │  timeout=30s │  │  timeout=45s │  │  timeout=60s │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

### Component Specifications

| Component | Technology | Scaling Strategy | Crash Prevention | AWS Pillar |
|-----------|-----------|-----------------|------------------|------------|
| API Service | FastAPI + Uvicorn | Horizontal (Railway replicas) | Graceful shutdown, health checks | Reliability, Perf |
| Database | PostgreSQL (Railway) | Vertical (plan upgrade) | Connection pooling, pool_pre_ping | Reliability |
| Job Queue | PostgreSQL async_jobs | Row-level locking, claim pattern | Atomic status transitions, max_attempts | Reliability |
| Service Gateway | In-process | Per-service semaphores | Circuit breakers, timeouts | Reliability, Perf |
| Auth | Supabase JWT + JWKS | Stateless (no session store) | JWKS cache with TTL, fallback | Security |
| Logging | Structured JSON | Log drain to Railway | Correlation IDs, error context | Ops Excellence |

### Railway Deployment Topology

```
Railway Project: resume-ai-app
├── api (FastAPI)
│   ├── Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
│   ├── Health: GET /health (shallow) + GET /health/ready (deep)
│   └── Env: DATABASE_URL, OPENAI_API_KEY, PERPLEXITY_API_KEY, FIRECRAWL_API_KEY
├── postgresql (managed)
│   └── Tables: users, resumes, jobs, tailored_resumes, async_jobs, ...
└── (future) worker
    ├── Start: python -m app.worker
    └── Shares DATABASE_URL with api
```

---

## 2. Backend Design Principles

### 2.1 Statelessness `[Reliability][Performance]`

All request state lives in the database or client token. No in-memory session state.

**Rules:**
- Authentication via JWT (Supabase) — token contains user identity
- Job progress stored in PostgreSQL `async_jobs` table, not in-memory dicts
- File uploads go to object storage, not local filesystem
- Configuration from environment variables, not runtime state

**Anti-patterns eliminated:**
- ~~`job_store = JobStore()` (in-memory dict)~~ → PostgreSQL `async_jobs` table
- ~~Global caches without TTL~~ → TTL-based caching with `time.monotonic()`

### 2.2 Database Access `[Reliability][Performance]`

**Connection Pool Configuration:**
```python
engine = create_async_engine(
    database_url,
    pool_size=10,        # Steady-state connections
    max_overflow=20,     # Burst capacity (total max: 30)
    pool_timeout=30,     # Wait for connection before error
    pool_pre_ping=True,  # Detect stale connections
    pool_recycle=300,    # Recycle every 5 minutes
)
```

**N+1 Prevention:**
- Use `selectinload()` for eager loading relationships
- Use `select().options(joinedload(...))` for single-query joins
- Never iterate results and issue per-row queries

### 2.3 Caching Strategy `[Performance][Cost]`

```
L1: In-process (TTL dict)     — JWKS keys, settings, hot data
L2: Redis (future)            — Session data, rate limits, AI result cache
L3: PostgreSQL                — Salary cache, company research, AI responses
L4: External API              — Fresh data (OpenAI, Perplexity, Firecrawl)
```

**Current Implementation (Tier 1 — no Redis):**
- JWKS public key: 6-hour in-process TTL
- Salary data: PostgreSQL `salary_cache` table with unique constraint
- Company research: Stored on `company_research` records
- AI results: Stored on `tailored_resumes`, `interview_preps`, `cover_letters`

### 2.4 Rate Limiting `[Reliability][Security]`

**Current:** slowapi with IP-based limits (10/hour for expensive ops)

**Target (Tier 2 — with Redis):**
```
Per-IP:       100 req/min (DDoS protection)
Per-User:     30 req/min (abuse prevention)
Per-Endpoint: Varies by cost:
  - /api/tailor/tailor:           5/hour
  - /api/interview-prep/generate: 5/hour
  - /api/cover-letters/generate:  10/hour
  - /api/career-path/generate:    3/hour
  - /api/resumes/upload:          20/hour
  - Read endpoints:               60/min
```

---

## 3. External Service Gateway

### 3.1 Circuit Breaker State Machine

```
                ┌────────────┐
                │   CLOSED   │ ← Normal operation
                │ (pass all) │
                └─────┬──────┘
                      │ failure_count >= threshold
                      ▼
                ┌────────────┐
                │    OPEN    │ ← Fail fast (no external calls)
                │ (reject)   │
                └─────┬──────┘
                      │ after recovery_timeout
                      ▼
                ┌────────────┐
                │ HALF_OPEN  │ ← Test with single request
                │ (1 probe)  │
                └──┬──────┬──┘
           success │      │ failure
                   ▼      ▼
              CLOSED     OPEN
```

### 3.2 Per-Service Configuration

| Service | Max Concurrent | Timeout | Retries | Circuit Threshold | Recovery |
|---------|---------------|---------|---------|-------------------|----------|
| OpenAI | 10 | 90s | 2 | 5 failures/60s | 30s |
| Perplexity | 5 | 30s | 2 | 3 failures/60s | 30s |
| Firecrawl | 3 | 45s | 1 | 3 failures/60s | 60s |
| Playwright | 2 | 60s | 1 | 2 failures/60s | 60s |

### 3.3 Retry Policy

```
Retry on: 429 (rate limit), 500, 502, 503, 504, ConnectionError, TimeoutError
Don't retry: 400, 401, 403, 404, 422 (client errors are terminal)

Backoff: exponential with jitter
  attempt 1: wait 1s ± 0.5s
  attempt 2: wait 2s ± 1.0s
  attempt 3: wait 4s ± 2.0s (if configured)

Special: 429 with Retry-After header → wait that many seconds
```

### 3.4 Gateway Call Flow

```
1. Check circuit breaker state
   → OPEN? Raise CircuitOpenError immediately
   → HALF_OPEN? Allow single probe request

2. Acquire semaphore (max concurrent per service)
   → Full? Wait up to 10s, then raise ConcurrencyLimitError

3. Execute with timeout
   → asyncio.wait_for(call, timeout=service_timeout)

4. On success:
   → Record success (circuit breaker)
   → Release semaphore
   → Return result

5. On retryable error:
   → Record failure (circuit breaker)
   → If retries remaining: backoff + retry from step 3
   → Else: release semaphore, raise

6. On terminal error:
   → Release semaphore
   → Raise immediately (no retry)
```

---

## 4. Client/UX Async Patterns

### 4.1 Polling Protocol

**Submit Job:**
```
POST /api/tailor/tailor-async
Body: { baseResumeId, jobUrl, ... }
Response: { jobId: "uuid", status: "pending" }
```

**Poll Status:**
```
GET /api/tailor/job/{jobId}
Response (pending):   { status: "pending",    progress: 0,  message: "Queued" }
Response (running):   { status: "processing", progress: 45, message: "Researching company..." }
Response (complete):  { status: "completed",  progress: 100, result: {...} }
Response (failed):    { status: "failed",     error: "OpenAI rate limit exceeded" }
```

**Polling Strategy:**
```
Interval: 2 seconds (configurable)
Max duration: 7 minutes (420s)
Backoff: On 429/503, double interval (max 30s)
Abort: On terminal error (400, 401, 403)
```

### 4.2 Error Classification

| HTTP Status | Classification | Client Action |
|-------------|---------------|---------------|
| 200-299 | Success | Process response |
| 400 | Terminal (bad request) | Show error, don't retry |
| 401 | Terminal (auth) | Redirect to login |
| 403 | Terminal (forbidden) | Show permission error |
| 404 | Terminal (not found) | Show not found |
| 408 | Retryable (timeout) | Retry with backoff |
| 422 | Terminal (validation) | Show validation errors |
| 429 | Retryable (rate limit) | Wait Retry-After, then retry |
| 500 | Retryable (server) | Retry with backoff (max 3) |
| 502 | Retryable (gateway) | Retry with backoff |
| 503 | Retryable (unavailable) | Retry with backoff |
| 504 | Retryable (timeout) | Retry with backoff |

### 4.3 Timeout Chain

```
Client timeout:  420s (7 min) — for AI operations
Gateway timeout: 120s — max time in service gateway
Service timeout:  90s — max time per external API call
DB timeout:       30s — max time waiting for connection

Rule: Each layer's timeout > inner layer's timeout + overhead
```

---

## 5. Concrete Code Examples

### 5.1 Async Route Handler with Job Enqueue

```python
@router.post("/tailor-async")
async def tailor_resume_async(
    request: TailorRequest,
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_unified),
):
    user, user_id = auth

    job_id = await job_manager.enqueue_job(
        db=db,
        job_type="tailor_resume",
        user_id=user_id,
        input_data={
            "base_resume_id": request.base_resume_id,
            "job_url": request.job_url,
            "company": request.company,
        },
    )

    return {"jobId": str(job_id), "status": "pending"}
```

### 5.2 Background Worker Job Processing

```python
async def process_tailor_job(job, db):
    """Process a tailor_resume job"""
    input_data = job.input_data
    gateway = get_gateway()

    # Step 1: Extract job details
    await job_manager.update_progress(db, job.id, 10, "Extracting job details...")
    job_details = await gateway.execute(
        "firecrawl",
        firecrawl_client.extract_job_details(input_data["job_url"])
    )

    # Step 2: Research company
    await job_manager.update_progress(db, job.id, 30, "Researching company...")
    research = await gateway.execute(
        "perplexity",
        perplexity.research_company(job_details["company"])
    )

    # Step 3: Tailor resume
    await job_manager.update_progress(db, job.id, 60, "Tailoring resume...")
    tailored = await gateway.execute(
        "openai",
        tailor_service.tailor_resume(base_resume, research, job_details)
    )

    return tailored
```

### 5.3 Service Gateway Usage

```python
from app.services.gateway import get_gateway

gateway = get_gateway()

# All external calls go through the gateway
result = await gateway.execute(
    service_name="openai",
    coroutine=client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[...],
    ),
)
```

### 5.4 Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Automatic fields: timestamp, correlation_id, user_id
logger.info("tailor.started", company="JPMorgan", job_title="PM")
logger.info("tailor.completed", duration_ms=4523, tokens_used=1200)
logger.error("tailor.failed", error="rate_limit", retry_after=60)
```

---

## 6. Monitoring & Load Testing

### 6.1 Metrics Catalog

| # | Metric | Type | Layer | Danger Threshold |
|---|--------|------|-------|-----------------|
| 1 | `http_requests_total` | Counter | API | - |
| 2 | `http_request_duration_seconds` | Histogram | API | p95 > 30s |
| 3 | `http_errors_total` | Counter | API | rate > 5%/2min |
| 4 | `ai_call_duration_seconds` | Histogram | Gateway | p95 > 60s |
| 5 | `ai_call_errors_total` | Counter | Gateway | rate > 10%/5min |
| 6 | `ai_call_active` | Gauge | Gateway | > max_concurrent |
| 7 | `circuit_breaker_state` | Gauge | Gateway | state=OPEN |
| 8 | `circuit_breaker_trips_total` | Counter | Gateway | > 3/hour |
| 9 | `job_queue_depth` | Gauge | Queue | > 100 |
| 10 | `job_processing_duration_seconds` | Histogram | Queue | p95 > 300s |
| 11 | `job_failures_total` | Counter | Queue | rate > 20%/hour |
| 12 | `db_pool_active` | Gauge | Database | > pool_size |
| 13 | `db_pool_overflow` | Gauge | Database | > 0 sustained |
| 14 | `db_query_duration_seconds` | Histogram | Database | p95 > 5s |
| 15 | `auth_failures_total` | Counter | Security | > 50/hour |

### 6.2 Alert Rules

| Alert | Condition | Window | Severity | Action |
|-------|-----------|--------|----------|--------|
| High Error Rate | error_rate > 5% | 2 min | Critical | Check gateway circuit states, recent deployments |
| Slow Responses | p95 latency > 30s | 5 min | Warning | Check AI service latency, DB pool |
| Queue Backlog | queue_depth > 100 | 3 min | Warning | Scale workers, check for stuck jobs |
| Circuit Open | any circuit = OPEN | Immediate | Critical | Check external service status pages |
| DB Pool Exhausted | active >= pool_size+overflow | 1 min | Critical | Kill long queries, increase pool |
| Auth Spike | auth_failures > 50/hr | 1 hour | Warning | Check for brute force, review WAF |

### 6.3 Load Test Template (Locust)

```python
from locust import HttpUser, task, between

class ResumeAIUser(HttpUser):
    wait_time = between(1, 5)

    def on_start(self):
        # Login and get JWT
        self.token = self.get_auth_token()

    @task(3)
    def browse_resumes(self):
        self.client.get("/api/resumes/",
            headers={"Authorization": f"Bearer {self.token}"})

    @task(1)
    def tailor_resume(self):
        resp = self.client.post("/api/tailor/tailor-async",
            json={"baseResumeId": 1, "jobUrl": "https://..."},
            headers={"Authorization": f"Bearer {self.token}"})
        job_id = resp.json().get("jobId")
        # Poll for completion
        for _ in range(30):
            status = self.client.get(f"/api/tailor/job/{job_id}",
                headers={"Authorization": f"Bearer {self.token}"})
            if status.json().get("status") in ("completed", "failed"):
                break
            time.sleep(2)
```

### 6.4 Capacity Planning

```
Current: ~10 concurrent users, ~50 AI calls/hour
Tier 1 capacity: ~50 concurrent users, ~200 AI calls/hour

Bottleneck analysis:
  DB connections: 30 (pool_size=10 + max_overflow=20) → handles ~50 concurrent
  OpenAI concurrency: 10 → ~10 parallel AI calls
  Perplexity concurrency: 5 → ~5 parallel research calls
  Total AI throughput: ~200 calls/hour (avg 90s/call, 10 concurrent)

Scale triggers:
  - DB pool consistently > 80% → increase pool_size
  - AI queue depth > 50 → add worker replicas
  - p95 latency > 30s → profile and optimize
```

---

## 7. Prioritization & Evolution Path

### Tier 1: Foundation (Week 1-2) — Current Implementation

| Item | Impact | Effort | Status |
|------|--------|--------|--------|
| AsyncOpenAI (fix event loop blocking) | Critical | 1 hour | Implementing |
| PostgreSQL job queue (replace in-memory) | Critical | 4 hours | Implementing |
| Structured logging + correlation IDs | High | 3 hours | Implementing |
| Service gateway (circuit breaker + semaphore) | High | 4 hours | Implementing |
| JWKS cache TTL | Medium | 30 min | Implementing |
| Debug endpoint gating | Medium | 15 min | Implementing |
| DB pool tuning | Medium | 15 min | Implementing |
| Health check (deep) | Medium | 1 hour | Implementing |
| Async job endpoints (dual endpoint pattern) | High | 3 hours | Implementing |
| Client polling hook | Medium | 2 hours | Implementing |

### Tier 2: Production Hardening (Month 2+)

| Item | Impact | Effort | Trigger |
|------|--------|--------|---------|
| Redis cache layer | High | 8 hours | AI costs > $100/mo or p95 > 15s |
| Horizontal scaling (worker service) | High | 4 hours | Queue depth > 50 sustained |
| Prometheus + Grafana dashboard | Medium | 6 hours | Need visibility into production |
| Rate limiting per user (Redis) | Medium | 4 hours | Abuse detected |
| AI response caching | High | 4 hours | Duplicate requests > 10% |
| WebSocket upgrade for jobs | Low | 8 hours | Poll interval < 2s needed |

### Tier 3: Scale (Month 6+)

| Item | Impact | Effort | Trigger |
|------|--------|--------|---------|
| Separate worker service (Railway) | High | 4 hours | > 1000 AI calls/day |
| CDN for static assets | Medium | 2 hours | Global users > 1000 |
| Read replicas | Medium | 4 hours | DB CPU > 70% sustained |
| Event-driven architecture (pub/sub) | Low | 16 hours | > 10 service integrations |

### Decision Tree

```
Current RPS?
├── < 100 RPS (current)
│   └── Tier 1 is sufficient
│       - AsyncOpenAI + job queue + gateway + logging
│       - Single Railway service
│
├── 100-1000 RPS
│   └── Add Tier 2
│       - Redis for caching + rate limiting
│       - Separate worker service
│       - Circuit breakers become critical
│       - Prometheus metrics dashboard
│
└── > 1000 RPS
    └── Add Tier 3
        - Horizontal scaling with load balancer
        - Read replicas for DB
        - Event-driven architecture
        - CDN for static content
        - Consider managed queue (SQS/Cloud Tasks)
```

### AWS Well-Architected Pillar Scores

| Pillar | Before | After Tier 1 | After Tier 2 | Notes |
|--------|--------|-------------|-------------|-------|
| Reliability | 2/5 | 4/5 | 4.5/5 | AsyncOpenAI, job queue, circuit breakers |
| Performance | 2/5 | 3.5/5 | 4.5/5 | Non-blocking, concurrency limits, caching |
| Ops Excellence | 2/5 | 3.5/5 | 4.5/5 | Structured logging, metrics, health checks |
| Cost Optimization | 2/5 | 3/5 | 4/5 | GPT-4.1-mini, result caching, quotas |
| Security | 3/5 | 4/5 | 4.5/5 | Debug gating, JWKS TTL, input validation |

---

## Appendix A: File Reference

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app, middleware stack, route registration |
| `app/config.py` | Environment-based settings (Pydantic) |
| `app/database.py` | SQLAlchemy async engine, session factory, migrations |
| `app/middleware/auth.py` | JWT/API-key/session auth with JWKS |
| `app/middleware/correlation.py` | Correlation ID generation and propagation |
| `app/services/gateway.py` | Circuit breaker, concurrency limiter, retry logic |
| `app/services/job_manager.py` | PostgreSQL-backed async job queue |
| `app/services/openai_tailor.py` | Resume tailoring with AsyncOpenAI |
| `app/services/perplexity_client.py` | Company research with Perplexity Sonar |
| `app/services/firecrawl_client.py` | Job extraction from URLs |
| `app/services/cover_letter_service.py` | Cover letter generation |
| `app/services/openai_interview_prep.py` | Interview prep with web research |
| `app/models/async_job.py` | SQLAlchemy model for job queue |
| `app/utils/logger.py` | Structured JSON logging with structlog |
| `app/utils/metrics.py` | In-process metrics (Prometheus compatible) |
| `app/worker.py` | Background job processor |

## Appendix B: Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `OPENAI_API_KEY` | Yes | OpenAI API key (GPT-4.1-mini) |
| `PERPLEXITY_API_KEY` | Yes | Perplexity API key (Sonar model) |
| `FIRECRAWL_API_KEY` | Yes | Firecrawl API key |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_JWT_SECRET` | No | HS256 JWT secret (ES256 uses JWKS) |
| `SUPABASE_ANON_KEY` | No | Supabase anonymous key |
| `DEBUG` | No | Enable debug mode (default: false) |
| `TEST_MODE` | No | Use mock AI responses (default: false) |
| `ALLOWED_ORIGINS` | No | CORS origins (comma-separated) |
| `PORT` | No | Server port (Railway provides this) |
