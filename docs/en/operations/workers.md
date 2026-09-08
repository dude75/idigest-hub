# Workers

The hub does **not** bundle transcription or summarization workers. Run them separately and register in **Instance → Workers**.

## Supported worker types

| type | Upstream project | Hub uses |
| ---- | ---------------- | -------- |
| `transcribe` | itranscribe-worker | POST `/transcribe`, GET/DELETE `/tasks/{id}`, GET `/health` |
| `summarize` | isummarize-worker | POST `/summarize`, GET/DELETE `/tasks/{id}`, GET `/health`, GET `/ready` |

## Registration

Instance admin POST `/workers`:

```json
{
  "type": "transcribe",
  "base_url": "http://10.0.0.5:8000",
  "api_token": "<worker API_TOKEN>",
  "weight": 1,
  "enabled": true
}
```

**Important:** `base_url` must be reachable from the **hub process**, not from the user's browser.

| Hub location | Worker on host |
| ------------ | -------------- |
| Docker container | `http://host.docker.internal:8000` |
| Same machine | `http://127.0.0.1:8000` |

## Authentication

Hub sends `Authorization: Bearer <decrypted api_token>` on every worker call. Users never see this token.

## Health and readiness

Dispatcher refreshes each node every ~5 seconds:

### Transcribe

- `GET {base_url}/health` → JSON with `engines` map
- Required engines from instance settings (default `asr_model=whisper`, `diarization_model=pyannote`)
- Engine status must be `loaded` for dispatch

Pool states: `ready`, `waiting` (engines loading — no timeout), `empty` (no nodes).

### Summarize

- `GET /health` for version/metadata
- `GET /ready` must return HTTP **200** to accept jobs

## Load balancing

Among ready nodes:

```
score = in_flight_tasks / max(weight, 1)
```

Pick lowest score. Higher `weight` receives more traffic when idle counts tie.

## Worker lifecycle from hub view

1. POST job → receive worker `task_id`
2. Poll GET until `success` or `error`
3. Copy result into hub DB (encrypted)
4. DELETE worker task (best effort on failure)

If GET returns 404 before hub persists → redispatch to another node.

## Metrics

Do **not** proxy worker `GET /metrics` through the hub. Scrape each worker directly with its `API_TOKEN`.

## Failure mapping

Worker error codes map to hub task errors (`pipeline_error`, `engine_unavailable`, `invalid_file`, …). See `WORKER_ERROR_MAP` in `app/services/workers.py`.

## Timeouts (.env)

| Variable | Default | Use |
| -------- | ------- | --- |
| `WORKER_HTTP_TIMEOUT_SEC` | 30 | Health, poll, delete |
| `WORKER_UPLOAD_TIMEOUT_SEC` | 300 | Transcribe upload, summarize POST |

## Related pages

- [Tasks domain](../domain/tasks.md)
- [Instance API](../api/instance.md)
- [README — Attach workers](../../../README.md#attach-workers)
