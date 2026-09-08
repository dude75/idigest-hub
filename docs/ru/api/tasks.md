# Tasks API

Требуется auth. Пользователь должен принадлежать org.

## POST `/tasks/transcribe`

**202 Accepted**

```json
{ "audio_id": "uuid" }
```

Audio должен существовать в org, быть доступен пользователю, файл присутствовать на диске.

Ответ: объект задачи с `task_id`, `status`, `type: "transcribe"` и т. д.

Ошибки: `not_found`, `insufficient_balance`, `forbidden`.

## POST `/tasks/summarize`

**202 Accepted**

```json
{
  "transcript_id": "uuid",
  "skill_ids": ["uuid", "uuid"]
}
```

Требуется минимум один skill. Каждый skill должен быть доступен (см. [Skills domain](../domain/skills.md)).

Ошибки: `not_found`, `forbidden`, `validation_error`, `insufficient_balance`.

## GET `/tasks`

Query-параметры:

| Param | Кто |
| ----- | --- |
| `org_id` | instance_admin |
| `user_id` | instance_admin или org_admin |

Ответ:

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

Дополнительные поля зависят от роли.

## GET `/tasks/{task_id}`

Опрос статуса задачи. Запускает dispatcher tick, когда queued/running.

При успехе:

- Transcribe: заполняется `transcript_id`
- Summarize: заполняется `summary_id`

При ошибке: `status: "error"`, `error: { "code": "..." }`

## DELETE `/tasks/{task_id}`

Отмена задачи в очереди (ещё не dispatched).

Успех: задача с `status: "error"`, `error.code: "canceled"`.

Ошибки: `not_found`, `forbidden`, `task_running`.

## Пример: pipeline transcribe

```bash
# Upload (session cookie или Bearer)
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

## Связанные страницы

- [Tasks domain](../domain/tasks.md)
- [Request flow](../architecture/request-flow.md)
