# Workers

The hub does **not** bundle transcription or summarization workers. Run them separately and register in **Instance → Workers**.

## Supported worker types

| type | Upstream project | Hub uses |
| ---- | ---------------- | -------- |
| `transcribe` | [itranscribe-worker](https://github.com/dude75/itranscribe-worker) | POST `/transcribe`, GET/DELETE `/tasks/{id}`, GET `/health` |
| `summarize` | [isummarize-worker](https://github.com/dude75/isummarize-worker) | POST `/summarize`, GET/DELETE `/tasks/{id}`, GET `/health`, GET `/ready` |

## Registration

Instance admin adds nodes in **Instance → Workers** (or POST `/workers`).

### Transcribe

1. Enter `base_url` and `api_token`.
2. **Test connection** (`POST /workers/probe`) — hub verifies the Bearer token (authorized `GET /tasks`) and reads models from `GET /health`.
3. Select one or more **ASR** models (`whisper`, `gigaam`, `parakeet`) and optionally **diarization** models (`nemo`, `pyannote`).
4. Save. At least one ASR model is required.

```json
{
  "type": "transcribe",
  "name": "GPU node 1",
  "base_url": "http://10.0.0.5:8000",
  "api_token": "<worker API_TOKEN>",
  "asr_models": ["whisper", "parakeet"],
  "diarization_models": ["pyannote"],
  "weight": 1,
  "enabled": true
}
```

On PATCH, omit `api_token` to keep the stored token. Re-test connection after URL/token changes.

### Summarize

```json
{
  "type": "summarize",
  "base_url": "http://10.0.0.6:8000",
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

- `GET {base_url}/health` → JSON with `engines` map (no token required)
- Hub maps engine IDs to ASR vs diarization (see [itranscribe-worker](https://github.com/dude75/itranscribe-worker))
- Each node stores the admin-selected subset in `asr_models_json` / `diarization_models_json`
- Dispatch uses the task’s snapshotted `asr_model` + optional `diarization_model` (from instance defaults and optional user override — see [Tasks](../domain/tasks.md))
- A node is a candidate only if it **offers** both models **and** reports them as `loaded` in `/health`

Pool states: `ready`, `waiting` (engines loading — no timeout), `empty` (no nodes).

**One task → one worker.** Hub does not split ASR and diarization across different nodes. If no single node has the full model set, the task stays `queued` (`waiting_engine`) until a matching node appears or `dispatch_timeout`.

### Summarize

- `GET /health` for version/metadata
- `GET /ready` must return HTTP **200** to accept jobs

## Load balancing

Among ready nodes with the **same required model set**:

```
score = in_flight_tasks / max(weight, 1)
```

Pick lowest score. Higher `weight` receives more traffic when idle counts tie.

Multiple transcribe workers may expose the same models — they compete as equal candidates and share load by score/weight.

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
