# Load Testing Guide

## Quick Start

```bash
pip install locust
cd backend
locust -f tests/load/locustfile.py --host https://YOUR-RAILWAY-URL
```

Open http://localhost:8089, set users and spawn rate, click **Start**.

## Configuration

| Env Var | Purpose | Default |
|---------|---------|---------|
| `LOAD_TEST_TOKEN` | Supabase JWT for auth | (empty — uses X-User-ID) |
| `LOAD_TEST_USER_ID` | Fallback user ID | `load-test` |
| `LOAD_TEST_RESUME_ID` | Base resume to tailor | `1` |

## What It Tests

1. **Health checks** — `/health` and `/health/ready`
2. **Resume listing** — `/api/resumes/list`
3. **Async tailoring** — `POST /api/tailor/tailor-async` → poll `GET /api/tailor/job/{id}`
4. **Metrics** — `/metrics`

## Interpreting Results

| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| p50 latency (health) | < 50ms | 50-200ms | > 200ms |
| p95 latency (tailor submit) | < 2s | 2-5s | > 5s |
| p95 latency (poll) | < 500ms | 500ms-2s | > 2s |
| Error rate | < 1% | 1-5% | > 5% |
| RPS (health) | > 50 | 20-50 | < 20 |

## Recommended Test Profiles

### Smoke (baseline)
```bash
locust --headless -u 5 -r 1 -t 60s
```

### Load (normal traffic)
```bash
locust --headless -u 20 -r 5 -t 300s
```

### Stress (find breaking point)
```bash
locust --headless -u 50 -r 10 -t 300s
```

## Acting on Results

- **High p95 on tailor-async submit**: Check gateway concurrency limits, DB pool size
- **High error rate on polling**: Check DB connection pool exhaustion, async_jobs table indexing
- **Circuit breaker opening**: External service (OpenAI/Perplexity) is degraded — check `/health/ready` circuit states
- **Timeouts**: Increase `pool_size` / `max_overflow` in database.py, or scale Railway instances
