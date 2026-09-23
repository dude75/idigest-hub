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

| Scope | MCP tools | REST API (Bearer JWT) |
| ----- | --------- | --------------------- |
| `transcripts:read` | `list_transcriptions`, `get_transcript` | `GET /transcripts`, `GET /transcripts/{id}` |
| `summaries:read` | `list_summaries`, `get_summary` | — (REST: session/PAT, без проверки scope) |
| `summaries:write` | `delete_summary` | — |
| `skills:read` | `list_skills` | — |
| `skills:write` | `update_skill` | — |
| `tasks:write` | `summarize_transcript` | — |

Проверка scope срабатывает при `via_oauth_token` (OAuth JWT). Cookie-сессия и PAT в REST подчиняются обычным правилам ролей, не этим scope.

Пример строки scope для полной автоматизации библиотеки:

```
transcripts:read summaries:read summaries:write skills:read skills:write tasks:write
```

## Tools

Каждый tool возвращает **строку с JSON** (UTF-8). Ошибки — через исключения tool (`PermissionError`, `ValueError` и т.д.).

| Tool | Параметры | Нужный scope |
| ---- | ---------- | ------------- |
| `list_transcriptions` | `include_hidden` (bool, по умолчанию `false`) | `transcripts:read` |
| `get_transcript` | `transcript_id` | `transcripts:read` |
| `list_summaries` | `include_hidden` (bool, по умолчанию `false`) | `summaries:read` |
| `get_summary` | `summary_id` | `summaries:read` |
| `delete_summary` | `summary_id` | `summaries:write` |
| `list_skills` | `scope` опционально: `base`, `org`, `self`, `shared` | `skills:read` |
| `update_skill` | `skill_id`, `name`, `body` | `skills:write` |
| `summarize_transcript` | `transcript_id`, `skill_ids` (непустой список) | `tasks:write` |

### Поведение

- **Списки** — не более **100** элементов, при большем объёме `"truncated": true`.
- **`get_transcript`** — `utterances` и метаданные видимых саммари (как `GET /transcripts/{id}`).
- **`list_summaries`** / **`get_summary`** — те же правила доступа, что в библиотеке; в списке нет текста саммари.
- **`delete_summary`** — владелец или org admin (как `DELETE /summaries/{id}`).
- **`list_skills`** — как `GET /skills` (поля `catalog`, `readonly`).
- **`update_skill`** — personal (владелец), org (org admin), base (instance admin). Shared/incoming не редактируются.
- **`summarize_transcript`** — ставит задачу **summarize** (аналог `POST /tasks/summarize`), возвращает JSON задачи. Нужны баланс/тариф и хотя бы один допустимый `skill_id`. Диспетчер работает асинхронно после ответа tool.

Код: `app/services/mcp_integration.py` (регистрация tools), `app/services/mcp_library.py` (логика как в REST).

## См. также

- [Auth & OAuth](auth.md)
- [Библиотека](library.md)
- [Задачи](tasks.md)
- [Skills](skills.md)
