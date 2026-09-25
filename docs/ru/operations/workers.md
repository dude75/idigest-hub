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

Имя LLM на хабе не выбирается. **Проверить подключение** читает его из `GET /health` (`model`, `llm_model` или `llm`, если это имя модели, а не статус вроде `ready`). В списке воркеров оно показывается как `summarize_model`. Нода, у которой в health нет имени модели, подходит под любую запрошенную модель summarize.

Default задаёт instance admin в **Instance → Settings → Сервисные модели**. Пользователь может переопределить его в **Profile**. Каждая новая задача summarize фиксирует разрешённое имя. Dispatch отправляет задачу только на включённые ноды, которые отдают это имя и возвращают `/ready` **200**. Если таких нет, задача остаётся `queued` с `meta.stage` `no_matching_worker`.

### Capture

Захват встреч требует **Instance → Settings** (`capture_enabled`, разрешённые connectors). Каталог connectors — объединение id из `/health` capture-воркеров (с label) и разрешённых на инстансе id (`jitsi`, `telemost`, `zoom`, …). Для **Jitsi** org admin задаёт **host** встречи (hostname + опционально JWT) в **Org → capture** — без привязки к конкретному воркеру.

1. Указать `base_url` и `api_token`.
2. **Проверить подключение** (`POST /workers/probe`) — hub проверяет Bearer-токен и читает connectors из `GET /health`.
3. Выбрать один или несколько **connectors**, которые обслуживает нода (подмножество разрешённых на инстансе со статусом `loaded` на воркере).
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

При старте capture hub выбирает включённую ноду с нужным connector (score/weight среди кандидатов). Для Jitsi используется конфиг host/JWT org; Telemost не требует карт host. Если у выбранной ноды нет ёмкости, hub может перевыбрать другую eligible-ноду до POST на воркер.

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

Колонка **Ёмкость** показывает `health.workers` ноды как `available / max`, если воркер отдал пул. Transcribe и summarize без `workers` откатываются к «здоровые включённые ноды / все ноды этого типа». Capture без `workers` показывает `1` или `0` из `1` (dispatch-ready или нет). У отключённых capture-нод в колонке `—`.

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

- `GET /health` для version/metadata и имени LLM (`model`, `llm_model` или `llm`)
- `GET /ready` должен вернуть HTTP **200**, чтобы принимать jobs
- Dispatch использует зафиксированный на задаче `snap_summarize_model` (default инстанса и опциональное переопределение пользователя — см. [Задачи](../domain/tasks.md))
- Нода — кандидат только если отдаёт эту модель (или в health нет имени модели) **и** `/ready` равен 200

### Capture

- `GET /health` → JSON с картой `connectors` (`id` → `{ "status": "loaded" | … }`)
- На ноде хранится выбранный админом подмножество в `capture_connectors_json`
- Нода dispatch-ready, если обслуживает connector из whitelist инстанса **и** отдаёт его как `loaded` (или connector в выбранном списке, если воркер не прислал status)
- Poll GET `/tasks/{id}` до готовности артефакта или ошибки; опционально POST `/tasks/{id}/stop`; артефакт — GET `/tasks/{id}/download`
- **Stop** (`POST /tasks/{id}/stop`): хаб ставит `meta.stop_requested` и просит воркер finalize. Poll продолжается в `finalizing` и при `canceled` на воркере, пока артефакт не готов или не истечёт `FINALIZING_STUCK_SEC` (по умолчанию **1200** с).
- **Cancel** (`DELETE /tasks/{id}`): задача помечается отменённой. Если артефакт на воркере уже готов — хаб всё равно скачивает его (salvage), затем `canceled`. DELETE на воркере — только после **успешного** persist на хабе (не при cancel).
- **Retry** (`POST /tasks/{id}/retry`) для `type: "capture"` **не поддерживается** (создайте новую capture-задачу).

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

## Удаление и потеря модели

Перед удалением, отключением или сменой, которая убирает модели, hub считает impact (`GET /workers/{id}/delete-impact`, `POST /workers/{id}/change-impact`).

| Тип | Что может сломаться | Замена |
| --- | -------------------- | ------ |
| `transcribe` | Default инстанса, переопределения пользователей, queued/running задачи, чья пара ASR+диаризация исчезнет | Другая пара, которую ещё отдают оставшиеся воркеры |
| `summarize` | То же для имени LLM из health воркера | Другая модель summarize, которую ещё отдают |
| `capture` | Queued/running capture с `worker_id` на этой ноде (особенно при снятии connector `jitsi` или удалении ноды) | Другой включённый capture-воркер с тем же connector (`jitsi` и т.д.) |

Если замена есть, UI (или `remediation` в PATCH/DELETE с `capture_worker_id`) переназначает затронутые capture-задачи. Строки Jitsi host org не привязаны к воркерам и **не** удаляются при delete воркера. Удаление без remediation снимает ноду и очищает `worker_id` у затронутых capture (running возвращаются в `queued`). См. [Instance API](../api/instance.md).

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
| `FINALIZING_STUCK_SEC` | 1200 | Макс. время в `finalizing` на воркере до ошибки capture на хабе |

## Связанные страницы

- [Tasks domain](../domain/tasks.md)
- [Instance API](../api/instance.md)
- [README — Attach workers](../../../README.ru.md#подключить-воркеры)
