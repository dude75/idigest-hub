# MCP (Model Context Protocol)

When [OAuth 2.1](auth.md#oauth-21-provider-mcp--open-webui) is enabled, the hub embeds an MCP **resource server** at **`/mcp`** (Streamable HTTP, stateless). Clients (e.g. Open WebUI) obtain JWT access tokens from the hub authorization server and call MCP tools over `/mcp`.

Tools follow the same access rules as the REST library, tasks, and skills APIs. Each tool returns a **JSON string** (UTF-8).

## Endpoints

| Method / path | Purpose |
| ------------- | ------- |
| `POST /mcp` or `POST /mcp/` | Streamable HTTP MCP (both accepted; canonical resource URL has **no** trailing slash) |
| `GET /.well-known/oauth-protected-resource/mcp` | Protected resource metadata: `resource`, `authorization_servers`, `scopes_supported` |
| `GET /.well-known/oauth-authorization-server` | Authorization server discovery |
| `GET /.well-known/jwks.json` | JWT signing keys |
| `POST /oauth/register` | Dynamic client registration (DCR) |
| `GET /oauth/authorize` | Authorization Code + PKCE S256 (browser HTML: login, consent, or error) |
| `POST /oauth/token` | Token exchange / refresh |

MCP accepts **hub-issued OAuth JWTs only** (not PAT `idg_…`). JWT access tokens also work as `Authorization: Bearer` on REST `/api/v1`.

## Authorization

Same rules as OAuth authorize in [auth.md](auth.md#oauth-21-provider-mcp--open-webui): org member or org admin, tariff `api_enabled`, account in good standing. **Instance admins without org membership cannot complete OAuth** (PAT may still be used for REST separately).

Browser authorize/consent uses styled HTML pages (same shell as web auth). Denied or blocked users see an HTML error (`api_disabled`, `oauth_org_membership_required`, `must_change_password`, `mfa_enrollment_required`, and similar). `/oauth/token` and `/oauth/register` stay JSON.

If the client omits `scope` on `/oauth/authorize`, the hub grants **every supported scope**. Request a space-separated subset to narrow the token.

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

Scope checks apply when `via_oauth_token` is true (OAuth JWT). Session cookies and PAT on REST are governed by normal role rules, not these scopes. On REST, OAuth JWT currently enforces **`transcripts:read`** on `GET /transcripts` and `GET /transcripts/{id}` only.

Example authorize scope string for full library automation:

```
audio:read audio:write transcripts:read transcripts:write summaries:read summaries:write skills:read skills:write tasks:write
```

## Tools (CRUD)

Errors surface as tool failures (`PermissionError`, `ValueError`, etc.) — not the REST error envelope.

| Entity | Create | Read | Update | Delete |
| ------ | ------ | ---- | ------ | ------ |
| **Audio** | `create_audio_upload`, `create_audio_import` | `list_audios`, `get_audio` | — | `delete_audio` |
| **Transcript** | — (via transcribe task / UI) | `list_transcripts`, `get_transcript` | `update_transcript` (`title`) | `delete_transcript` |
| **Summary** | `create_summary` (async task) | `list_summaries`, `get_summary` | `update_summary` (`title`, `body`) | `delete_summary` |
| **Skill** | `create_skill` | `list_skills`, `get_skill` | `update_skill` | `delete_skill` |

### Audio

| Tool | Parameters | Scope | Returns |
| ---- | ---------- | ----- | ------- |
| `list_audios` | `include_hidden` (bool, default `false`) | `audio:read` | `{ "items": [audio + derived flags], "truncated": bool }` |
| `get_audio` | `audio_id` | `audio:read` | Audio + `transcripts[]` (visible) + `can_transcribe` |
| `create_audio_upload` | `filename`, `content_base64` (standard or data-URL base64) | `audio:write` | Created audio (same shape as REST upload) |
| `create_audio_import` | `url`, `transcribe` (bool, default `false`), `skill_ids` optional | `tasks:write` | **Task** JSON (import or capture) |
| `get_task` | `task_id` | `tasks:write` | **Task** JSON (same as `GET /tasks/{id}`; tick when `queued`/`running`) |
| `stop_capture_task` | `task_id` | `tasks:write` | **Capture task** JSON after stop request (same as `POST /tasks/{id}/stop`) |
| `delete_audio` | `audio_id` | `audio:write` | `{ "status": "ok" }` |

List derived flags: `has_transcript`, `has_summary`, `transcript_id`, `summary_transcript_id`.

### Transcripts

| Tool | Parameters | Scope | Returns |
| ---- | ---------- | ----- | ------- |
| `list_transcripts` | `include_hidden` (bool, default `false`) | `transcripts:read` | `{ "items": [transcript + `has_summary`], "truncated": bool }` — no utterances |
| `get_transcript` | `transcript_id` | `transcripts:read` | Transcript + `utterances` + visible `summaries[]` (metadata, no body) |
| `update_transcript` | `transcript_id`, `title` | `transcripts:write` | Updated transcript |
| `delete_transcript` | `transcript_id` | `transcripts:write` | `{ "status": "ok" }` |

### Summaries

| Tool | Parameters | Scope | Returns |
| ---- | ---------- | ----- | ------- |
| `list_summaries` | `include_hidden` (bool, default `false`) | `summaries:read` | `{ "items": [summary metadata], "truncated": bool }` — no body |
| `get_summary` | `summary_id` | `summaries:read` | Summary including `body` |
| `create_summary` | `transcript_id`, `skill_ids` (non-empty list) | `tasks:write` | **Task** JSON (`type: "summarize"`) |
| `update_summary` | `summary_id`, `title` optional, `body` optional (at least one required) | `summaries:write` | Updated summary including body |
| `delete_summary` | `summary_id` | `summaries:write` | `{ "status": "ok" }` |

### Skills

| Tool | Parameters | Scope | Returns |
| ---- | ---------- | ----- | ------- |
| `list_skills` | `scope` optional: `base`, `org`, `self`, `shared` | `skills:read` | `{ "items": [skill + `catalog`, `readonly`] }` (no 100-item cap) |
| `get_skill` | `skill_id` | `skills:read` | Skill including `body`, plus `catalog` / `readonly` |
| `create_skill` | `name`, `body`, `catalog` optional: `self` (default), `org`, `base` | `skills:write` | Created skill |
| `update_skill` | `skill_id`, `name`, `body` | `skills:write` | Updated skill |
| `delete_skill` | `skill_id` | `skills:write` | `{ "status": "ok" }` |

### Behavior notes

- **List tools** (audio / transcripts / summaries) cap at **100** items and set `"truncated": true` when the library has more. `list_skills` is uncapped (same as `GET /skills`).
- Visibility matches REST: owner + shares; org admin sees all org rows; `include_hidden` includes the caller’s hidden items.
- **`create_audio_upload`**: `.wav`, `.mp3`, `.m4a` only (extension + magic bytes, same as REST); max size follows org tariff (capped at 1 GiB).
- **`create_audio_import`**: same rules as `POST /tasks/import` (may enqueue import or capture). Returns task JSON until audio exists. Optional `transcribe` + `skill_ids` start the pipeline after import.
- **`get_task`**: same as `GET /tasks/{id}`. Dispatcher tick for active tasks, **except** running capture with a live background thread (see REST).
- **`stop_capture_task`**: same as `POST /tasks/{id}/stop`. Running **capture** only; the background thread sends worker stop when present (not DELETE cancel).
- **`delete_audio`** / **`delete_transcript`**: org admin only (same as REST wipe).
- **`create_summary`**: enqueues a **summarize** task (like `POST /tasks/summarize`); dispatcher runs asynchronously after the tool returns. LLM is the user’s summarize model or the instance default — not a tool parameter.
- **`update_transcript`**: owner or org admin (rename only).
- **`update_summary`** / **`delete_summary`**: owner or org admin. Body edit sets `edited=true`.
- **`create_skill`** / **`update_skill`** / **`delete_skill`**: `self` = owner; `org` = org admin; `base` = instance admin (same as REST catalogs).

Implementation: `app/services/mcp_integration.py` (tool registration), `app/services/mcp_library.py` (business logic aligned with REST).

## Related

- [Auth & OAuth](auth.md)
- [Library](library.md)
- [Tasks](tasks.md)
- [Skills](skills.md)
- [Roles and access](../domain/roles-and-access.md)
