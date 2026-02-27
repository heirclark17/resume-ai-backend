# Alert Rules

Production alert definitions for the ResumeAI backend. Each rule includes a threshold, evaluation window, and a short runbook.

---

## Critical (Page immediately)

### 1. Error Rate > 5%

- **Metric**: HTTP 5xx responses / total responses
- **Window**: 2 minutes
- **Threshold**: > 5%
- **Runbook**: Check `/health/ready` for degraded services. Review structured logs for the correlation IDs of failing requests. If a circuit breaker is open, the external service (OpenAI/Perplexity/Firecrawl) is down — wait for recovery or switch to fallback.

### 2. Circuit Breaker Open

- **Metric**: `GET /health/ready` → `checks.circuits.{service}` = `"open"`
- **Window**: Immediate
- **Runbook**: The service will auto-recover after the recovery timeout (30-60s). If it stays open, check the external service's status page. Consider increasing `circuit_failure_threshold` in `gateway.py` if false positives occur.

### 3. Database Unreachable

- **Metric**: `GET /health/ready` → `checks.database` != `"ok"`
- **Window**: Immediate
- **Runbook**: Check Railway Postgres service status. Verify connection string in environment variables. Check if pool is exhausted (`pool_size=10, max_overflow=20`).

---

## Warning (Investigate within 1 hour)

### 4. p95 Latency > 30 seconds

- **Metric**: `GET /metrics` → `histograms.openai.duration_ms.p95`
- **Window**: 5 minutes
- **Threshold**: > 30,000ms
- **Runbook**: OpenAI is responding slowly. Check OpenAI status page. Consider reducing `max_tokens` in prompts or switching to gpt-4.1-mini for non-critical calls.

### 5. Job Queue Depth > 100

- **Metric**: `GET /health/ready` → `checks.queue_depth`
- **Window**: 3 minutes
- **Threshold**: > 100 pending/processing jobs
- **Runbook**: Worker is falling behind. Check if worker process is running. Consider scaling to a dedicated worker Railway service. Verify no stuck jobs (status = `processing` for > 10 minutes).

### 6. High Concurrency Saturation

- **Metric**: `GET /metrics` → `counters.openai.error` increasing rapidly
- **Window**: 5 minutes
- **Runbook**: Too many concurrent AI calls. Review `GATEWAY_CONFIG` semaphore limits. If legitimate traffic, increase `max_concurrent` for the affected service.

---

## Info (Review daily)

### 7. Slow Poll Responses

- **Metric**: `GET /metrics` → poll endpoint p95 > 2s
- **Window**: 15 minutes
- **Runbook**: Add index on `async_jobs(status, created_at)` if not present. Check DB connection pool usage.

### 8. Retry Rate > 10%

- **Metric**: `counters.{service}.error` / (`counters.{service}.success` + `counters.{service}.error`)
- **Window**: 15 minutes
- **Runbook**: External service is flaky. Check Retry-After headers. Consider increasing backoff in gateway config.

---

## Monitoring Endpoints

| Endpoint | Purpose | Frequency |
|----------|---------|-----------|
| `GET /health` | Shallow liveness (Railway routing) | 10s |
| `GET /health/ready` | Deep readiness (DB + queue + circuits) | 30s |
| `GET /metrics` | In-process counters + histograms | 60s |

## Railway Log Drain

All structured logs are JSON with `correlation_id`. Configure Railway log drain to forward to your observability platform (Datadog, Grafana Cloud, etc.) and create dashboards from the `metrics.call` log events.
