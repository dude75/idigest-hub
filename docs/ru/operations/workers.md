# Воркеры

Hub **не** включает воркеры транскрипции или суммаризации. Запускайте их отдельно и регистрируйте в **Instance → Workers**.

## Поддерживаемые типы воркеров

| type | Upstream-проект | Использует hub |
| ---- | --------------- | -------------- |
| `transcribe` | itranscribe-worker | POST `/transcribe`, GET/DELETE `/tasks/{id}`, GET `/health` |
| `summarize` | isummarize-worker | POST `/summarize`, GET/DELETE `/tasks/{id}`, GET `/health`, GET `/ready` |

## Регистрация

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

**Важно:** `base_url` должен быть достижим из **процесса hub**, а не из браузера пользователя.

| Расположение hub | Воркер на хосте |
| ---------------- | --------------- |
| Docker container | `http://host.docker.internal:8000` |
| Same machine | `http://127.0.0.1:8000` |

## Аутентификация

Hub отправляет `Authorization: Bearer <decrypted api_token>` при каждом вызове воркера. Пользователи никогда не видят этот token.

## Health и readiness

Dispatcher обновляет каждый узел примерно каждые 5 секунд:

### Transcribe

- `GET {base_url}/health` → JSON с картой `engines`
- Требуемые engines из настроек instance (по умолчанию `asr_model=whisper`, `diarization_model=pyannote`)
- Статус engine должен быть `loaded` для dispatch

Состояния пула: `ready`, `waiting` (engines загружаются — без таймаута), `empty` (нет узлов).

### Summarize

- `GET /health` для version/metadata
- `GET /ready` должен вернуть HTTP **200**, чтобы принимать jobs

## Балансировка нагрузки

Среди готовых узлов:

```
score = in_flight_tasks / max(weight, 1)
```

Выбирается наименьший score. Больший `weight` получает больше трафика при равном количестве idle.

## Жизненный цикл воркера с точки зрения hub

1. POST job → получить worker `task_id`
2. Poll GET до `success` или `error`
3. Скопировать результат в hub DB (encrypted)
4. DELETE worker task (best effort при ошибке)

Если GET возвращает 404 до того, как hub сохранил результат → redispatch на другой узел.

## Метрики

**Не** проксируйте worker `GET /metrics` через hub. Снимайте метрики с каждого воркера напрямую с его `API_TOKEN`.

## Маппинг ошибок

Коды ошибок воркера мапятся на ошибки задач hub (`pipeline_error`, `engine_unavailable`, `invalid_file`, …). См. `WORKER_ERROR_MAP` в `app/services/workers.py`.

## Таймауты (.env)

| Variable | Default | Назначение |
| -------- | ------- | ---------- |
| `WORKER_HTTP_TIMEOUT_SEC` | 30 | Health, poll, delete |
| `WORKER_UPLOAD_TIMEOUT_SEC` | 300 | Transcribe upload, summarize POST |

## Связанные страницы

- [Tasks domain](../domain/tasks.md)
- [Instance API](../api/instance.md)
- [README — Attach workers](../../../README.ru.md#подключить-воркеры)
