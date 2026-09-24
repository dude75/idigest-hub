# MCP (Model Context Protocol)

При включённом [OAuth 2.1](auth.md#oauth-21-provider-mcp--open-webui) хаб поднимает встроенный MCP **resource server** на **`/mcp`** (Streamable HTTP, stateless). Клиенты (например Open WebUI) получают JWT access token у authorization server хаба и вызывают MCP tools через `/mcp`.

Tools подчиняются тем же правилам доступа, что REST API библиотеки, задач и skills. Каждый tool возвращает **строку с JSON** (UTF-8).

## Эндпоинты

| Метод / путь | Назначение |
| ------------ | ---------- |
| `POST /mcp` или `POST /mcp/` | Streamable HTTP MCP (оба варианта; канонический resource URL **без** `/` в конце) |
| `GET /.well-known/oauth-protected-resource/mcp` | Метаданные protected resource: `resource`, `authorization_servers`, `scopes_supported` |
| `GET /.well-known/oauth-authorization-server` | Discovery authorization server |
| `GET /.well-known/jwks.json` | Ключи подписи JWT |
| `POST /oauth/register` | Dynamic client registration (DCR) |
| `GET /oauth/authorize` | Authorization Code + PKCE S256 (браузерный HTML: логин, consent или ошибка) |
| `POST /oauth/token` | Обмен кода / refresh |

MCP принимает **только OAuth JWT**, выданные хабом (не PAT `idg_…`). JWT access token также работает как `Authorization: Bearer` в REST `/api/v1`.

## Авторизация

Те же правила, что для OAuth authorize в [auth.md](auth.md#oauth-21-provider-mcp--open-webui): участник или админ org, на тарифе `api_enabled`, аккаунт без блокировок. **Instance admin без членства в org не может пройти OAuth** (PAT для REST по-прежнему возможен отдельно).

Браузерный authorize/consent — стилизованные HTML-страницы (тот же shell, что у web auth). При отказе пользователь видит HTML-ошибку (`api_disabled`, `oauth_org_membership_required`, `must_change_password`, `mfa_enrollment_required` и аналоги). `/oauth/token` и `/oauth/register` остаются JSON.

Если клиент не передаёт `scope` в `/oauth/authorize`, хаб выдаёт **все поддерживаемые scope**. Чтобы сузить токен, перечислите нужные scope через пробел.

## OAuth scopes

| Scope | MCP tools |
| ----- | --------- |
| `audio:read` | `list_audios`, `get_audio` |
| `audio:write` | `create_audio_upload`, `delete_audio` |
| `transcripts:read` | `list_transcripts`, `get_transcript` |
| `transcripts:write` | `update_transcript`, `delete_transcript` |
| `summaries:read` | `list_summaries`, `get_summary` |
| `summaries:write` | `update_summary`, `delete_summary` |
| `skills:read` | `list_skills`, `get_skill` |
| `skills:write` | `create_skill`, `update_skill`, `delete_skill` |
| `tasks:write` | `create_audio_import`, `create_summary`, `get_task`, `stop_capture_task` |

Проверка scope срабатывает при `via_oauth_token` (OAuth JWT). Cookie-сессия и PAT в REST подчиняются обычным правилам ролей, не этим scope. В REST OAuth JWT сейчас проверяет **`transcripts:read`** только на `GET /transcripts` и `GET /transcripts/{id}`.

Пример строки scope для полной автоматизации библиотеки:

```
audio:read audio:write transcripts:read transcripts:write summaries:read summaries:write skills:read skills:write tasks:write
```

## Tools (CRUD)

Ошибки — через исключения tool (`PermissionError`, `ValueError` и т.д.), не через REST error envelope.

| Сущность | Create | Read | Update | Delete |
| -------- | ------ | ---- | ------ | ------ |
| **Аудио** | `create_audio_upload`, `create_audio_import` | `list_audios`, `get_audio` | — | `delete_audio` |
| **Транскрипт** | — (задача transcribe / UI) | `list_transcripts`, `get_transcript` | `update_transcript` (`title`) | `delete_transcript` |
| **Саммари** | `create_summary` (async task) | `list_summaries`, `get_summary` | `update_summary` (`title`, `body`) | `delete_summary` |
| **Skill** | `create_skill` | `list_skills`, `get_skill` | `update_skill` | `delete_skill` |

### Аудио

| Tool | Параметры | Scope | Ответ |
| ---- | --------- | ----- | ----- |
| `list_audios` | `include_hidden` (bool, по умолчанию `false`) | `audio:read` | `{ "items": [audio + флаги], "truncated": bool }` |
| `get_audio` | `audio_id` | `audio:read` | Аудио + `transcripts[]` (видимые) + `can_transcribe` |
| `create_audio_upload` | `filename`, `content_base64` (standard или data-URL) | `audio:write` | Созданное аудио (как REST upload) |
| `create_audio_import` | `url`, `transcribe` (bool, по умолчанию `false`), `skill_ids` опционально | `tasks:write` | JSON **задачи** (import или capture) |
| `get_task` | `task_id` | `tasks:write` | JSON **задачи** (как `GET /tasks/{id}`; tick при `queued`/`running`) |
| `stop_capture_task` | `task_id` | `tasks:write` | JSON **задачи** capture после запроса stop (как `POST /tasks/{id}/stop`) |
| `delete_audio` | `audio_id` | `audio:write` | `{ "status": "ok" }` |

Флаги списка: `has_transcript`, `has_summary`, `transcript_id`, `summary_transcript_id`.

### Транскрипты

| Tool | Параметры | Scope | Ответ |
| ---- | --------- | ----- | ----- |
| `list_transcripts` | `include_hidden` (bool, по умолчанию `false`) | `transcripts:read` | `{ "items": [транскрипт + `has_summary`], "truncated": bool }` — без utterances |
| `get_transcript` | `transcript_id` | `transcripts:read` | Транскрипт + `utterances` + видимые `summaries[]` (метаданные, без body) |
| `update_transcript` | `transcript_id`, `title` | `transcripts:write` | Обновлённый транскрипт |
| `delete_transcript` | `transcript_id` | `transcripts:write` | `{ "status": "ok" }` |

### Саммари

| Tool | Параметры | Scope | Ответ |
| ---- | --------- | ----- | ----- |
| `list_summaries` | `include_hidden` (bool, по умолчанию `false`) | `summaries:read` | `{ "items": [метаданные], "truncated": bool }` — без body |
| `get_summary` | `summary_id` | `summaries:read` | Саммари включая `body` |
| `create_summary` | `transcript_id`, `skill_ids` (непустой список) | `tasks:write` | JSON **задачи** (`type: "summarize"`) |
| `update_summary` | `summary_id`, `title` опционально, `body` опционально (нужно хотя бы одно) | `summaries:write` | Обновлённое саммари включая body |
| `delete_summary` | `summary_id` | `summaries:write` | `{ "status": "ok" }` |

### Skills

| Tool | Параметры | Scope | Ответ |
| ---- | --------- | ----- | ----- |
| `list_skills` | `scope` опционально: `base`, `org`, `self`, `shared` | `skills:read` | `{ "items": [skill + `catalog`, `readonly`] }` (без лимита 100) |
| `get_skill` | `skill_id` | `skills:read` | Skill включая `body`, плюс `catalog` / `readonly` |
| `create_skill` | `name`, `body`, `catalog` опционально: `self` (по умолчанию), `org`, `base` | `skills:write` | Созданный skill |
| `update_skill` | `skill_id`, `name`, `body` | `skills:write` | Обновлённый skill |
| `delete_skill` | `skill_id` | `skills:write` | `{ "status": "ok" }` |

### Поведение

- **Списки** audio / transcripts / summaries — не более **100** элементов, при большем объёме `"truncated": true`. `list_skills` без лимита (как `GET /skills`).
- Видимость как в REST: владелец + shares; org admin видит все строки org; `include_hidden` включает скрытые элементы вызывающего.
- **`create_audio_upload`**: только `.wav`, `.mp3`, `.m4a` (расширение + magic bytes); лимит размера по тарифу org (потолок 1 GiB).
- **`create_audio_import`**: как `POST /tasks/import` (import или capture). Пока нет файла — JSON задачи. Опционально `transcribe` + `skill_ids` запускают пайплайн после импорта.
- **`get_task`**: как `GET /tasks/{id}`. Dispatcher tick для активных задач, **кроме** running capture с живым фоновым потоком (см. REST).
- **`stop_capture_task`**: как `POST /tasks/{id}/stop`. Running **capture** only; worker stop делает фоновый поток, если он есть (не `DELETE` cancel).
- **`delete_audio`** / **`delete_transcript`**: только org admin.
- **`create_summary`** — ставит задачу **summarize** (аналог `POST /tasks/summarize`); диспетчер работает асинхронно. LLM — summarize model пользователя или дефолт инстанса, не параметр tool.
- **`update_transcript`**: владелец или org admin (только title).
- **`update_summary`** / **`delete_summary`**: владелец или org admin. Правка body ставит `edited=true`.
- **`create_skill`** / **`update_skill`** / **`delete_skill`**: `self` — владелец; `org` — org admin; `base` — instance admin (как REST-каталоги).

Код: `app/services/mcp_integration.py` (регистрация tools), `app/services/mcp_library.py` (логика как в REST).

## См. также

- [Auth & OAuth](auth.md)
- [Библиотека](library.md)
- [Задачи](tasks.md)
- [Skills](skills.md)
- [Роли и доступ](../domain/roles-and-access.md)
