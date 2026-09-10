# Мониторинг (Prometheus / Grafana)

On-prem заказчик поднимает свой Prometheus и Grafana. В репозитории — **endpoint метрик хаба**, имена метрик, JSON дашборда Grafana и пример scrape-конфига.

Воркеры (`itranscribe-worker`, `isummarize-worker`) мониторятся **из своих репозиториев** — не проксируйте worker `/metrics` через хаб.

## Endpoint

```
GET /metrics
Authorization: Bearer <METRICS_TOKEN>   # если задан METRICS_TOKEN
```

| Переменная | По умолчанию | Смысл |
| ---------- | ------------ | ----- |
| `METRICS_ENABLED` | `true` | Прикладные метрики. `false` / `0` / `no` — только process collectors. |
| `METRICS_TOKEN` | пусто | Bearer для scrape. Пусто — без auth (в production задайте). |

## Префикс метрик

Прикладные метрики: префикс `idigest_hub_`.

| Метрика | Тип | Labels | Назначение |
| ------- | --- | ------ | ---------- |
| `idigest_hub_up` | Gauge | — | Процесс отдаёт `/metrics` |
| `idigest_hub_ready` | Gauge | — | БД ok, dispatcher loop жив |
| `idigest_hub_tasks_queued` | Gauge | `type` | Задачи в очереди |
| `idigest_hub_tasks_running` | Gauge | `type` | Задачи в работе |
| `idigest_hub_tasks_total` | Counter | `type`, `status`, `error_code` | Terminal-задачи |
| `idigest_hub_task_duration_seconds` | Histogram | `type` | `queued_at` → terminal |
| `idigest_hub_oldest_queued_age_seconds` | Gauge | `type` | Возраст oldest queued |
| `idigest_hub_worker_up` | Gauge | `node_id`, `type`, `name` | Воркер достижим из хаба |
| `idigest_hub_worker_health_age_seconds` | Gauge | `node_id` | С последнего health poll |
| `idigest_hub_worker_pool_state` | Gauge | `type`, `state` | `ready` / `waiting` / `empty` (one-hot) |
| `idigest_hub_dispatcher_tick_seconds` | Histogram | — | Длительность tick |
| `idigest_hub_dispatcher_tick_errors_total` | Counter | — | Ошибки tick |
| `idigest_hub_http_requests_total` | Counter | `method`, `route`, `status` | HTTP (без scrape `/metrics`) |
| `idigest_hub_http_request_duration_seconds` | Histogram | `method`, `route` | Latency HTTP |

Плюс стандартные `process_*` и `python_*`.

**Cardinality:** `route` — шаблон FastAPI (`/api/v1/tasks/{task_id}`), не UUID. Без label `org_id` / `user_id` / `task_id`.

## Scrape Prometheus

Пример: [`deploy/prometheus/scrape.example.yml`](../../../deploy/prometheus/scrape.example.yml).

```yaml
scrape_configs:
  - job_name: idigest-hub
    metrics_path: /metrics
    authorization:
      credentials: "${IDIGEST_HUB_METRICS_TOKEN}"
    static_configs:
      - targets: ["hub.internal:8080"]
```

Не выставляйте `/metrics` на публичный ingress без auth. Предпочтительно internal scrape или localhost за nginx.

## Grafana

Импорт [`grafana/dashboards/idigest-hub.json`](../../../grafana/dashboards/idigest-hub.json):

1. Grafana → Dashboards → New → Import
2. Загрузить JSON
3. Выбрать datasource Prometheus
4. UID дашборда: `idigest-hub`

Панели: очередь, throughput/ошибки задач, health воркеров (view хаба), dispatcher, HTTP, process.

## Пример алертов

| Alert | Expression |
| ----- | ---------- |
| HubDown | `up{job="idigest-hub"} == 0` |
| HubNotReady | `idigest_hub_ready == 0` |
| QueueStuck | `sum(idigest_hub_tasks_queued) > 0 and sum(rate(idigest_hub_tasks_total{status="success"}[15m])) == 0` |
| NoWorkersUp | `sum(idigest_hub_worker_up) == 0 and count(idigest_hub_worker_up) > 0` |
| HighTaskErrors | `sum(rate(idigest_hub_tasks_total{status="error"}[5m])) / sum(rate(idigest_hub_tasks_total[5m])) > 0.1` |
| StaleWorkerHealth | `max(idigest_hub_worker_health_age_seconds) > 120` |

## См. также

- [Деплой](deployment.md)
- [Воркеры](workers.md) — метрики воркеров отдельно
- [README — Метрики](../../../README.ru.md#метрики-prometheus--grafana)
