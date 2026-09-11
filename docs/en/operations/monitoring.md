# Monitoring (Prometheus / Grafana)

On-prem customers run their own Prometheus and Grafana. This repo ships the **hub metrics endpoint**, metric names, a Grafana dashboard JSON, and an example scrape config.

Workers (`itranscribe-worker`, `isummarize-worker`) are monitored from **their own repositories** — do not proxy worker `/metrics` through the hub.

## Endpoint

```
GET /metrics
Authorization: Bearer <METRICS_TOKEN>   # required
```

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `METRICS_ENABLED` | `true` | Application metrics. `false` / `0` / `no` = process collectors only. |
| `METRICS_TOKEN` | empty | Bearer for scrape. Required; empty = `/metrics` returns 401. |

## Metric prefix

All application metrics use the `idigest_hub_` prefix.

| Metric | Type | Labels | Purpose |
| ------ | ---- | ------ | ------- |
| `idigest_hub_up` | Gauge | — | Process serves `/metrics` |
| `idigest_hub_ready` | Gauge | — | DB ok and dispatcher loop healthy |
| `idigest_hub_tasks_queued` | Gauge | `type` | Queued tasks |
| `idigest_hub_tasks_running` | Gauge | `type` | Running tasks |
| `idigest_hub_tasks_total` | Counter | `type`, `status`, `error_code` | Terminal tasks |
| `idigest_hub_task_duration_seconds` | Histogram | `type` | `queued_at` → terminal |
| `idigest_hub_oldest_queued_age_seconds` | Gauge | `type` | Oldest queued task age |
| `idigest_hub_worker_up` | Gauge | `node_id`, `type`, `name` | Registered worker reachable from hub |
| `idigest_hub_worker_health_age_seconds` | Gauge | `node_id` | Since last health poll |
| `idigest_hub_worker_pool_state` | Gauge | `type`, `state` | `ready` / `waiting` / `empty` (one-hot) |
| `idigest_hub_dispatcher_tick_seconds` | Histogram | — | Dispatcher tick duration |
| `idigest_hub_dispatcher_tick_errors_total` | Counter | — | Tick failures |
| `idigest_hub_http_requests_total` | Counter | `method`, `route`, `status` | HTTP (excludes `/metrics` scrapes) |
| `idigest_hub_http_request_duration_seconds` | Histogram | `method`, `route` | HTTP latency |

Plus standard `process_*` and `python_*` collectors.

**Cardinality:** `route` is the FastAPI path template (e.g. `/api/v1/tasks/{task_id}`), not raw UUIDs. No `org_id` / `user_id` / `task_id` labels.

## Prometheus scrape

Example: [`deploy/prometheus/scrape.example.yml`](../../../deploy/prometheus/scrape.example.yml).

```yaml
scrape_configs:
  - job_name: idigest-hub
    metrics_path: /metrics
    authorization:
      credentials: "${IDIGEST_HUB_METRICS_TOKEN}"
    static_configs:
      - targets: ["hub.internal:8080"]
```

Do not expose `/metrics` on a public ingress without auth. Prefer internal network scrape or bind the hub to localhost behind nginx.

## Grafana

Import [`grafana/dashboards/idigest-hub.json`](../../../grafana/dashboards/idigest-hub.json):

1. Grafana → Dashboards → New → Import
2. Upload JSON or paste file contents
3. Select the Prometheus datasource
4. Dashboard UID: `idigest-hub`

Panels cover queue depth, task throughput/errors, worker health (hub view), dispatcher, HTTP, and process stats.

## Suggested alerts

| Alert | Expression |
| ----- | ---------- |
| HubDown | `up{job="idigest-hub"} == 0` |
| HubNotReady | `idigest_hub_ready == 0` |
| QueueStuck | `sum(idigest_hub_tasks_queued) > 0 and sum(rate(idigest_hub_tasks_total{status="success"}[15m])) == 0` |
| NoWorkersUp | `sum(idigest_hub_worker_up) == 0` and `count(idigest_hub_worker_up) > 0` |
| HighTaskErrors | `sum(rate(idigest_hub_tasks_total{status="error"}[5m])) / sum(rate(idigest_hub_tasks_total[5m])) > 0.1` |
| StaleWorkerHealth | `max(idigest_hub_worker_health_age_seconds) > 120` |

## Related

- [Deployment](deployment.md)
- [Workers](workers.md) — worker metrics are separate
- [README — Metrics](../../../README.md#metrics-prometheus--grafana)
