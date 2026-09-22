# Воркеры

Hub **не** включает воркеры транскрипции, суммаризации или захвата встреч. Запускайте их отдельно и регистрируйте в **Instance → Workers**.

## Поддерживаемые типы воркеров

| type | Upstream-проект | Использует hub |
| ---- | --------------- | -------------- |
| `transcribe` | [itranscribe-worker](https://github.com/dude75/itranscribe-worker) | POST `/transcribe`, GET/DELETE `/tasks/{id}`, GET `/health` |
| `summarize` | [isummarize-worker](https://github.com/dude75/isummarize-worker) | POST `/summarize`, GET/DELETE `/tasks/{id}`, GET `/health`, GET `/ready` |
| `capture` | [icapture-worker](https://github.com/dude75/icapture-worker) | POST `/capture`, GET/POST `/tasks/{id}`, GET `/tasks/{id}/download`, DELETE `/tasks/{id}`, GET `/health` |

## Регистрация

Instance admin добавляет ноды в **Instance → Workers** (или POST `/workers`).

### Transcribe

1. Указать `base_url` и `api_token`.
2. **Проверить подключение** (`POST /workers/probe`) — hub проверяет Bearer-токен (авторизованный `GET /tasks`) и читает модели из `GET /health`.
3. Выбрать одну или несколько моделей **ASR** (`whisper`, `gigaam`, `parakeet`) и при необходимости **диаризации** (`nemo`, `pyannote`).
4. Сохранить. Нужна хотя бы одна ASR-модель.

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

При PATCH можно не передавать `api_token`, чтобы сохранить текущий. После смены URL/токена — повторная проверка подключения.

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

Захват встреч требует **Instance → Settings** (`capture_enabled`, разрешённые connectors) и привязки Jitsi host → worker на уровне org — см. настройки инстанса в UI.

1. Указать `base_url` и `api_token`.
2. **Проверить подключение** (`POST /workers/probe`) — hub проверяет Bearer-токен и читает connectors из `GET /health`.
3. Выбрать один или несколько **connectors**, которые обслуживает нода (`jitsi`, `zoom`, … — подмножество разрешённых на инстансе и со статусом `loaded` на воркере).
4. Сохранить. Нужен хотя бы один connector.

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

Capture-задачи привязаны к worker, выбранному для host встречи org; hub не балансирует один capture между несколькими нодами.

**Важно:** `base_url` должен быть достижим из **процесса hub**, а не из браузера пользователя.

| Расположение hub | Воркер на хосте |
| ---------------- | --------------- |
| Docker container | `http://host.docker.internal:8000` |
| Same machine | `http://127.0.0.1:8000` |

## Аутентификация

Hub отправляет `Authorization: Bearer <decrypted api_token>` при каждом вызове воркера. Пользователи никогда не видят этот token.

## Единый блок `workers` в GET /health

Все типы воркеров (**itranscribe**, **isummarize**, **icapture**) могут отдавать одну и ту же структуру ёмкости:

```json
"workers": {
  "max": 4,
  "active": 1,
  "available": 3
}
```

| Поле | Смысл |
| ---- | ----- |
| `max` | Размер пула на этом процессе |
| `active` | Задач в работе |
| `available` | Свободных workers в пуле (`> 0` — можно слать job) |

Hub **суммирует** `workers.*` по включённым и dispatch-ready нодам данного типа. Если ни одна нода не отдаёт `workers`, для типа используется fallback: **готовые hub-ноды / включённые** (legacy: одна активная job на ноду, если пул неизвестен).

`GET /workers` отдаёт агрегаты `{transcribe,summarize,capture}_capacity` той же формы для UI instance admin.

Дополнительно по типам: transcribe — `engines`; summarize — `GET /ready` (200); capture — `connectors` (connector `loaded` для платформы задачи и выбранного на ноде подмножества).

Если на ноде есть `workers.available`, новые capture на этой ноде стартуют только при `available > 0`; иначе действует legacy-правило (вторая активная capture на той же ноде не запускается).

## Health и readiness

Dispatcher обновляет каждый узел примерно каждые 5 секунд:

### Transcribe

- `GET {base_url}/health` → JSON с картой `engines` (без токена)
- Hub различает ASR и диаризацию по id engine (см. [itranscribe-worker](https://github.com/dude75/itranscribe-worker))
- На каждой ноде хранится выбранный админом поднабор в `asr_models_json` / `diarization_models_json`
- Dispatch использует зафиксированные на задаче `snap_asr_model` и опционально `snap_diarization_model` (defaults инстанса + переопределение пользователя — см. [Задачи](../domain/tasks.md))
- Нода — кандидат только если **обслуживает** обе нужные модели **и** отдаёт их как `loaded` в `/health`

Состояния пула: `ready`, `waiting` (engines загружаются — без таймаута), `empty` (нет узлов).

**Одна задача → один воркер.** Hub не собирает ASR с одной ноды и диаризацию с другой. Если ни у одной ноды нет полного набора моделей, задача остаётся `queued` (`waiting_engine`), пока не появится подходящая нода или не сработает `dispatch_timeout`.

### Summarize

- `GET /health` для version/metadata
- `GET /ready` должен вернуть HTTP **200**, чтобы принимать jobs

### Capture

- `GET /health` → JSON с картой `connectors` (`id` → `{ "status": "loaded" | … }`)
- На ноде хранится выбранный админом подмножество в `capture_connectors_json`
- Нода dispatch-ready, если обслуживает connector из whitelist инстанса **и** отдаёт его как `loaded` (или connector в выбранном списке, если воркер не прислал status)
- Poll GET `/tasks/{id}` до терминального состояния; опционально POST `/tasks/{id}/stop`; артефакт — GET `/tasks/{id}/download`

## Балансировка нагрузки

Среди готовых узлов с **одинаковым требуемым набором моделей**:

```
score = in_flight_tasks / max(weight, 1)
```

Выбирается наименьший score. Больший `weight` получает больше трафика при равном количестве idle.

Несколько transcribe-воркеров могут обслуживать один и тот же набор моделей — они конкурируют как равные кандидаты и делят нагрузку по score/weight.

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
| `WORKER_UPLOAD_TIMEOUT_SEC` | 300 | Transcribe upload, summarize POST, capture download |
| `WORKER_CAPTURE_TIMEOUT_SEC` | 660 | Capture POST `/capture` (блокируется до join) |

## Связанные страницы

- [Tasks domain](../domain/tasks.md)
- [Instance API](../api/instance.md)
- [README — Attach workers](../../../README.ru.md#подключить-воркеры)
