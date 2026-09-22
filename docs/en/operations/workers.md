# Workers

The hub does **not** bundle transcription, summarization, or meeting-capture workers. Run them separately and register in **Instance → Workers**.

## Supported worker types

| type | Upstream project | Hub uses |
| ---- | ---------------- | -------- |
| `transcribe` | [itranscribe-worker](https://github.com/dude75/itranscribe-worker) | POST `/transcribe`, GET/DELETE `/tasks/{id}`, GET `/health` |
| `summarize` | [isummarize-worker](https://github.com/dude75/isummarize-worker) | POST `/summarize`, GET/DELETE `/tasks/{id}`, GET `/health`, GET `/ready` |
| `capture` | [icapture-worker](https://github.com/dude75/icapture-worker) | POST `/capture`, GET/POST `/tasks/{id}`, GET `/tasks/{id}/download`, DELETE `/tasks/{id}`, GET `/health` |

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

### Capture

Meeting capture requires **Instance → Settings** (`capture_enabled`, allowed connectors) and org-level Jitsi host → worker mapping — see instance settings in the UI.

1. Enter `base_url` and `api_token`.
2. **Test connection** (`POST /workers/probe`) — hub verifies the Bearer token and reads connectors from `GET /health`.
3. Select one or more **connectors** the node should serve (`jitsi`, `zoom`, … — subset of instance-allowed connectors with status `loaded` on the worker).
4. Save. At least one connector is required.

```json
{
  "type": "capture",
  "name": "Capture node 1",
  "base_url": "http://10.0.0.7:8000",
  "api_token": "<worker API_TOKEN>",
  "capture_connectors": ["jitsi"],
  "weight": 1,
  "enabled": true
}
```

Capture tasks are bound to the worker chosen for the org’s meeting host; the hub does not load-balance capture across nodes for a single task.

**Important:** `base_url` must be reachable from the **hub process**, not from the user's browser.

| Hub location | Worker on host |
| ------------ | -------------- |
| Docker container | `http://host.docker.internal:8000` |
| Same machine | `http://127.0.0.1:8000` |

## Authentication

Hub sends `Authorization: Bearer <decrypted api_token>` on every worker call. Users never see this token.

## Shared `workers` block in GET /health

All worker types (**itranscribe**, **isummarize**, **icapture**) may expose the same capacity shape:

```json
"workers": {
  "max": 4,
  "active": 1,
  "available": 3
}
```

| Field | Meaning |
| ----- | ------- |
| `max` | Pool size for this process |
| `active` | Jobs in flight |
| `available` | Free workers in the pool (`> 0` means the hub may dispatch) |

The hub **sums** `workers.*` across enabled, dispatch-ready nodes of that type. If no node returns `workers`, the type falls back to **ready hub nodes / enabled** (legacy: one in-flight job per node when the pool is unknown).

`GET /workers` exposes aggregated `{transcribe,summarize,capture}_capacity` with the same shape for the instance admin UI.

Type-specific checks still apply: transcribe — `engines`; summarize — `GET /ready` (200); capture — `connectors` (connector `loaded` for the task’s platform and the node’s selected subset).

When `workers.available` is present on a node, new capture jobs on that node start only if `available > 0`; otherwise the hub uses the legacy rule (no second active capture on the same node).

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

### Capture

- `GET /health` → JSON with `connectors` map (`id` → `{ "status": "loaded" | … }`)
- Hub stores the admin-selected subset in `capture_connectors_json`
- A node is dispatch-ready if it offers the connector required by the instance whitelist **and** reports it as `loaded` (or the connector is in the selected list when the worker omits status)
- Poll GET `/tasks/{id}` until terminal state; optional POST `/tasks/{id}/stop`; download artifact via GET `/tasks/{id}/download`

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
| `WORKER_UPLOAD_TIMEOUT_SEC` | 300 | Transcribe upload, summarize POST, capture download |
| `WORKER_CAPTURE_TIMEOUT_SEC` | 660 | Capture POST `/capture` (blocks until join completes) |

## Related pages

- [Tasks domain](../domain/tasks.md)
- [Instance API](../api/instance.md)
- [README — Attach workers](../../../README.md#attach-workers)
