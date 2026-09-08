# Поток запросов

На этой странице описано, как HTTP-запросы проходят через аутентификацию, создание задач и фоновый dispatcher.

## Пути аутентификации

```mermaid
sequenceDiagram
  participant C as Клиент
  participant H as Hub API
  participant DB as Database

  alt Session cookie
    C->>H: Cookie hub_session=...
    H->>DB: Lookup sessions.token_hash
    H->>DB: Load user, membership, org
    H->>H: Slide expires_at (+14 days)
  else Bearer API token
    C->>H: Authorization: Bearer ...
    H->>DB: Lookup api_tokens.token_hash
    H->>H: enforce_bearer_api rate limits
    Note over H: Cookie sessions are NOT API-rate-limited
  end
```

Разрешение выполняется в `app/deps.py` → `resolve_auth()`. При ошибках возвращается HTTP **401** с `error.code = unauthorized` (или `must_change_password`, `api_disabled` для Bearer).

### Session sliding

Middleware в `app/main.py` повторно выставляет session cookie при успешных ответах, если браузер ещё не получил новый `Set-Cookie`. Каждый аутентифицированный запрос продлевает `expires_at` на `SESSION_TTL_SEC` (14 days).

## Поток задачи transcribe

```mermaid
sequenceDiagram
  participant U as Пользователь
  participant API as POST /tasks/transcribe
  participant D as Dispatcher
  participant W as transcribe worker
  participant DB as Database

  U->>API: audio_id
  API->>DB: Create Task status=queued, snap_* from tariff
  API->>D: locked_tick(task_id)
  D->>DB: Refresh worker health (cached 5s)
  D->>D: Pick node (weight + in-flight load)
  D->>W: POST /transcribe (multipart file)
  W-->>D: 202/200 + worker task_id
  D->>DB: status=running, worker_task_id set
  loop Poll until terminal
    D->>W: GET /tasks/{worker_task_id}
    W-->>D: queued | running | success | error
  end
  D->>DB: Encrypt utterances → Transcript
  D->>DB: apply_success_charge, status=success
  D->>W: DELETE /tasks/{worker_task_id}
  U->>API: GET /tasks/{id}
  API-->>U: transcript_id, status=success
```

### Состояния пула (transcribe)

Перед dispatch dispatcher классифицирует пул transcribe:

| State | Значение |
| ----- | -------- |
| `ready` | Хотя бы один включённый узел имеет ASR + diarization engines в состоянии `loaded` |
| `waiting` | Включённые узлы есть, но engines loading/unavailable — **без dispatch timeout** (`retry_without_timeout=true`) |
| `empty` | Нет включённых узлов или ни один не соответствует требуемым models |

Если пул остаётся `empty` дольше `DISPATCH_NO_CANDIDATE_SEC` (по умолчанию 3600s), задача завершается с ошибкой `error.code = dispatch_timeout`.

## Поток задачи summarize

Аналогично transcribe, но:

1. Хаб расшифровывает utterances транскрипта и форматирует их строками `speaker: text`
2. Skills загружаются по `skill_ids`, объединяются секциями `## name\n\nbody`
3. Размер payload = transcript UTF-8 + skills UTF-8; максимум `MAX_SUMMARIZE_PAYLOAD_BYTES` (10 MiB)
4. Пул воркеров использует `GET /ready` (HTTP 200) вместо engine map
5. Биллинг: фиксированная плата за job + единицы per-1000-character **выходного** текста summary

## Poll on read

`GET /tasks/{task_id}` вызывает `locked_tick`, когда `status` равен `queued` или `running`. UI polling и API-клиенты получают более быстрый отклик, не дожидаясь только фонового цикла.

Фоновый цикл (`dispatcher_loop`) обрабатывает **все** задачи в статусах queued/running каждые `DISPATCH_POLL_SEC` и также выполняет audio retention purge.

## Worker 404 redispatch

Если poll возвращает **404** от воркера и хаб ещё не сохранил результат:

- Очищаются `worker_id` / `worker_task_id`
- `status` возвращается в `queued`
- На следующем tick dispatch идёт на другой узел

Если у хаба уже есть `produced_transcript_id` или `produced_summary_id`, 404 игнорируется (race при cleanup).

## Cancel

`DELETE /tasks/{task_id}` разрешён только когда:

- `status == queued`
- `worker_task_id` ещё null (задача ещё не отправлена на воркер)

Устанавливается `status=error`, `error.code=canceled`. После dispatch cancel отклоняется с `task_running`.

## Распространение ошибок

Ошибки воркера маппятся через `WORKER_ERROR_MAP` в `app/services/workers.py` на hub-facing коды в задаче (`pipeline_error`, `engine_unavailable`, `invalid_file` и т.д.). См. [API errors](../api/README.md#error-codes).

## Связанные страницы

- [Tasks](../domain/tasks.md)
- [Workers](../operations/workers.md)
- [Billing](../domain/billing.md)
