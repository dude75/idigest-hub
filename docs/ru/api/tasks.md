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

Требуется минимум один skill. Каждый skill должен быть доступен (см. [Skills domain](../domain/skills.md)). Имя LLM в теле не передаётся: hub фиксирует модель summarize пользователя или default инстанса (см. [Задачи](../domain/tasks.md)).

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

Опрос статуса задачи. Запускает dispatcher tick, когда `queued`/`running`, **кроме** running **capture** с активным фоновым потоком хаба (poll идёт из потока; tick нужен только если потока нет — recovery).

## GET `/tasks`

Список active/done. Tick по active — с тем же правилом для capture (см. выше).

При успехе:

- Transcribe: заполняется `transcript_id`
- Summarize: заполняется `summary_id`

При ошибке: `status: "error"`, `error: { "code": "..." }`

## POST `/tasks/{task_id}/stop`

**202 Accepted** — только **capture** в `running`: мягкая остановка записи (`meta.stop_requested`), затем finalize и download на воркере. Не то же самое, что отмена через DELETE.

Пока жив фоновый capture-поток, HTTP stop на воркер шлёт поток; иначе — хаб сразу + dispatcher tick.

Ошибки: `not_found`, `forbidden`, `validation_error` (не capture), `task_running` (не running).

## DELETE `/tasks/{task_id}`

Отмена: **import** / **capture** в `queued` или `running`; **transcribe** / **summarize** — только `queued` без `worker_task_id`.

Успех: `status: "error"`, `error.code: "canceled"`. Для capture с активным фоновым потоком DELETE на воркер делает поток (как при stop).

Ошибки: `not_found`, `forbidden`, `task_running` (transcribe/summarize уже на воркере).

## POST `/tasks/{task_id}/retry`

**202 Accepted**

Повторная постановка упавшей задачи (`status: "error"`) в очередь. Сбрасывает worker refs и ошибку, затем сразу запускает tick диспетчера.

Недоступно для терминальных ошибок: `canceled`, `source_deleted`, `text_too_long`, `payload_too_large`, `invalid_file`, `invalid_url`.

Исходник должен существовать (audio, transcript, URL import). Баланс проверяется снова.

Ошибки: `not_found`, `forbidden`, `task_running`, `validation_error`, `insufficient_balance`, `import_disabled`.

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

Эквиваленты MCP: [MCP tools](mcp.md) — `create_audio_import`, `create_summary`, `get_task`, `stop_capture_task`. Scope: `tasks:write`.

## Связанные страницы

- [Tasks domain](../domain/tasks.md)
- [Request flow](../architecture/request-flow.md)
- [MCP tools](mcp.md)
