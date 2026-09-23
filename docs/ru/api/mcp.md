# MCP (Model Context Protocol)

При включённом [OAuth 2.1](auth.md#oauth-21-provider-mcp--open-webui) хаб поднимает встроенный MCP **resource server** на **`/mcp`** (Streamable HTTP). Клиенты (например Open WebUI) получают JWT access token у authorization server хаба и вызывают MCP tools через `/mcp`.

Метаданные protected resource:

```
GET /.well-known/oauth-protected-resource/mcp
```

В ответе: `resource`, `authorization_servers`, `scopes_supported`.

## Авторизация

Те же правила, что для OAuth authorize в [auth.md](auth.md#oauth-21-provider-mcp--open-webui): участник или админ org, на тарифе `api_enabled`, аккаунт без блокировок. **Instance admin без членства в org не может пройти OAuth** (PAT для REST по-прежнему возможен отдельно).

MCP принимает **только OAuth JWT**, выданные хабом (не PAT `idg_…`).

Если клиент не передаёт `scope` в `/oauth/authorize`, по умолчанию выдаётся только **`transcripts:read`**. Перечислите все нужные scope через пробел.

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
| `tasks:write` | `create_audio_import`, `create_summary` |

Проверка scope срабатывает при `via_oauth_token` (OAuth JWT). Cookie-сессия и PAT в REST подчиняются обычным правилам ролей, не этим scope.

Пример строки scope для полной автоматизации библиотеки:

```
audio:read audio:write transcripts:read transcripts:write summaries:read summaries:write skills:read skills:write tasks:write
```

## Tools (CRUD)

Каждый tool возвращает **строку с JSON** (UTF-8). Ошибки — через исключения tool (`PermissionError`, `ValueError` и т.д.).

| Сущность | Create | Read | Update | Delete |
| -------- | ------ | ---- | ------ | ------ |
| **Аудио** | `create_audio_upload`, `create_audio_import` | `list_audios`, `get_audio` | — | `delete_audio` |
| **Транскрипт** | — (задача transcribe / UI) | `list_transcripts`, `get_transcript` | `update_transcript` (`title`) | `delete_transcript` |
| **Саммари** | `create_summary` (async task) | `list_summaries`, `get_summary` | `update_summary` (`title`, `body`) | `delete_summary` |
| **Skill** | `create_skill` | `list_skills`, `get_skill` | `update_skill` | `delete_skill` |

### Параметры

| Tool | Параметры | Scope |
| ---- | ---------- | ----- |
| `list_audios` | `include_hidden` (bool, по умолчанию `false`) | `audio:read` |
| `get_audio` | `audio_id` | `audio:read` |
| `create_audio_upload` | `filename`, `content_base64` (standard или data-URL) | `audio:write` |
| `create_audio_import` | `url`, `transcribe` (bool), `skill_ids` опционально | `tasks:write` |
| `delete_audio` | `audio_id` | `audio:write` |
| `list_transcripts` | `include_hidden` (bool, по умолчанию `false`) | `transcripts:read` |
| `get_transcript` | `transcript_id` | `transcripts:read` |
| `update_transcript` | `transcript_id`, `title` | `transcripts:write` |
| `delete_transcript` | `transcript_id` | `transcripts:write` |
| `list_summaries` | `include_hidden` (bool, по умолчанию `false`) | `summaries:read` |
| `get_summary` | `summary_id` | `summaries:read` |
| `create_summary` | `transcript_id`, `skill_ids` (непустой список) | `tasks:write` |
| `update_summary` | `summary_id`, `title` опционально, `body` опционально | `summaries:write` |
| `delete_summary` | `summary_id` | `summaries:write` |
| `list_skills` | `scope` опционально: `base`, `org`, `self`, `shared` | `skills:read` |
| `get_skill` | `skill_id` | `skills:read` |
| `create_skill` | `name`, `body`, `catalog` опционально: `self` (по умолчанию), `org`, `base` | `skills:write` |
| `update_skill` | `skill_id`, `name`, `body` | `skills:write` |
| `delete_skill` | `skill_id` | `skills:write` |

### Поведение

- **Списки** — не более **100** элементов, при большем объёме `"truncated": true`.
- **`create_audio_upload`**: только `.wav`, `.mp3`, `.m4a`; лимит размера по тарифу org.
- **`create_audio_import`**: как `POST /tasks/import` (import или capture); пока нет файла — JSON задачи.
- **`delete_audio`**: только org admin.
- **`get_transcript`** — `utterances` и метаданные видимых саммари (как `GET /transcripts/{id}`).
- **`create_summary`** — ставит задачу **summarize** (аналог `POST /tasks/summarize`); диспетчер работает асинхронно.
- **`update_transcript`** / **`delete_transcript`** — как REST (удаление только org admin).
- **`list_skills`** — как `GET /skills` (поля `catalog`, `readonly`).

Код: `app/services/mcp_integration.py` (регистрация tools), `app/services/mcp_library.py` (логика как в REST).

## См. также

- [Auth & OAuth](auth.md)
- [Библиотека](library.md)
- [Задачи](tasks.md)
- [Skills](skills.md)
