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

At least one skill required. Each skill must be accessible (see [Skills domain](../domain/skills.md)).

Errors: `not_found`, `forbidden`, `validation_error`, `insufficient_balance`.

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

Poll task status. Triggers dispatcher tick when queued/running.

On success:

- Transcribe: `transcript_id` populated
- Summarize: `summary_id` populated

On failure: `status: "error"`, `error: { "code": "..." }`

## DELETE `/tasks/{task_id}`

Cancel queued task (not yet dispatched).

Success: task with `status: "error"`, `error.code: "canceled"`.

Errors: `not_found`, `forbidden`, `task_running`.

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

## Related pages

- [Tasks domain](../domain/tasks.md)
- [Request flow](../architecture/request-flow.md)
