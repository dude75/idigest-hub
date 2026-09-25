# Tasks API

Auth required. User must belong to an org.

## POST `/tasks/transcribe`

**202 Accepted**

```json
{ "audio_id": "uuid" }
```

Audio must exist in org, be readable by user, file present on disk.

Response: task object with `task_id`, `status`, `type: "transcribe"`, etc.

Errors: `not_found`, `insufficient_balance`, `forbidden`.

## POST `/tasks/summarize`

**202 Accepted**

```json
{
  "transcript_id": "uuid",
  "skill_ids": ["uuid", "uuid"]
}
```

At least one skill required. Each skill must be accessible (see [Skills domain](../domain/skills.md)). The LLM name is not in the body: the hub snapshots the user’s summarize model or the instance default (see [Tasks domain](../domain/tasks.md)).

Errors: `not_found`, `forbidden`, `validation_error`, `insufficient_balance`.

## POST `/tasks/import`

**202 Accepted**

```json
{
  "url": "https://…",
  "transcribe": false,
  "skill_ids": [],
  "bot_display_name": "Optional bot name"
}
```

URL import (YouTube, etc.) when the host matches configured extractors, or **meeting capture** when capture is enabled and the URL matches an allowed connector (`jitsi`, `telemost`, …). Capture jobs get `type: "capture"`; file imports get `type: "import"`. Optional `transcribe` + `skill_ids` chain transcribe after success. `bot_display_name` overrides user/org capture bot name for that job only.

Errors: `import_disabled`, `capture_disabled`, `validation_error`, `insufficient_balance`, task errors such as `meeting_host_not_configured` (Jitsi host not mapped for org).

## POST `/tasks/capture`

**202 Accepted** — explicit capture (same pipeline as import when URL routes to capture):

```json
{
  "meeting_url": "https://…",
  "pin": "",
  "transcribe": false,
  "skill_ids": [],
  "bot_display_name": null
}
```

`pin` is used for connectors that require it (not Telemost). Requires `capture_enabled`.

## GET `/capture/platforms`

Auth required. Discovery for library import/capture UI and agents:

```json
{
  "enabled": true,
  "connectors": [{ "id": "jitsi", "label": "Jitsi Meet" }],
  "jitsi_hosts": ["meet.example.com"]
}
```

`connectors` lists instance-allowed connectors (labels from worker health when available). `jitsi_hosts` lists org-mapped Jitsi hostnames when capture and `jitsi` are enabled.

## GET `/tasks`

Query parameters:

| Param | Who |
| ----- | --- |
| `org_id` | instance_admin |
| `user_id` | instance_admin or org_admin |

Response:

```json
{
  "items": [
    {
      "task_id": "...",
      "type": "transcribe",
      "status": "running",
      "meta": { "stage": "running" },
      "transcript_id": null,
      "summary_id": null,
      "error": null,
      "owner_email": "user@example.com",
      "org_name": "team",
      "audio_filename": "meeting.mp3"
    }
  ]
}
```

Extra fields depend on role.

## GET `/tasks/{task_id}`

Poll task status. Triggers a dispatcher tick when `queued`/`running`, **except** running **capture** while the hub’s background capture thread is active (the thread polls; a tick runs only when the thread is gone — recovery).

## GET `/tasks`

Active/done lists. Ticks on active tasks follow the same capture rule as above.

On success:

- Transcribe: `transcript_id` populated
- Summarize: `summary_id` populated

On failure: `status: "error"`, `error: { "code": "..." }`

## POST `/tasks/{task_id}/stop`

**202 Accepted** — **capture** in `running` only: graceful stop (`meta.stop_requested`), then finalize and download on the worker. Not the same as cancel via DELETE.

While the background capture thread is alive, it sends worker stop; otherwise the hub stops immediately and schedules a dispatcher tick.

Errors: `not_found`, `forbidden`, `validation_error` (not capture), `task_running` (not running).

## DELETE `/tasks/{task_id}`

Cancel: **import** / **capture** in `queued` or `running`; **transcribe** / **summarize** — only `queued` with no `worker_task_id`.

Success: `status: "error"`, `error.code: "canceled"`. For capture with an active background thread, worker DELETE is handled by the thread (same idea as stop).

Errors: `not_found`, `forbidden`, `task_running` (transcribe/summarize already on a worker).

## POST `/tasks/{task_id}/retry`

**202 Accepted**

Re-queue a failed task (`status: "error"`). Resets worker refs and error state, then runs an immediate dispatcher tick.

Not allowed for terminal errors such as `canceled`, `source_deleted`, `text_too_long`, `payload_too_large`, `invalid_file`, `invalid_url`.

Source must still exist (audio, transcript, import URL). Balance is checked again.

Errors: `not_found`, `forbidden`, `task_running`, `validation_error`, `insufficient_balance`, `import_disabled`.

## Example: transcribe pipeline

```bash
# Upload (session cookie or Bearer)
curl -sS -b cookies.txt -F "file=@meeting.mp3" \
  http://127.0.0.1:8080/api/v1/audios

# Start task
curl -sS -b cookies.txt -X POST \
  -H "Content-Type: application/json" \
  -d '{"audio_id":"AUDIO_UUID"}' \
  http://127.0.0.1:8080/api/v1/tasks/transcribe

# Poll
curl -sS -b cookies.txt \
  http://127.0.0.1:8080/api/v1/tasks/TASK_UUID
```

MCP equivalents: [MCP tools](mcp.md) — `list_capture_platforms`, `create_audio_import`, `create_transcribe`, `create_summary`, `get_task`, `stop_capture_task`. Scope: `tasks:write`.

## Related pages

- [Tasks domain](../domain/tasks.md)
- [Request flow](../architecture/request-flow.md)
- [MCP tools](mcp.md)
