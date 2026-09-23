# MCP (Model Context Protocol)

When [OAuth 2.1](auth.md#oauth-21-provider-mcp--open-webui) is enabled, the hub embeds an MCP **resource server** at **`/mcp`** (Streamable HTTP). Clients (e.g. Open WebUI) obtain JWT access tokens from the hub authorization server and call MCP tools over `/mcp`.

Protected resource metadata:

```
GET /.well-known/oauth-protected-resource/mcp
```

Returns `resource`, `authorization_servers`, and `scopes_supported`.

## Authorization

Same rules as OAuth authorize in [auth.md](auth.md#oauth-21-provider-mcp--open-webui): org member or org admin, tariff `api_enabled`, account in good standing. **Instance admins without org membership cannot complete OAuth** (PAT may still be used for REST separately).

MCP accepts **hub-issued OAuth JWTs only** (not PAT `idg_…`).

If the client omits `scope` on `/oauth/authorize`, the hub defaults to **`transcripts:read`** only. Request every scope your integration needs, space-separated.

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

Scope checks apply when `via_oauth_token` is true (OAuth JWT). Session cookies and PAT on REST are governed by normal role rules, not these scopes.

Example authorize scope string for full library automation:

```
audio:read audio:write transcripts:read transcripts:write summaries:read summaries:write skills:read skills:write tasks:write
```

## Tools (CRUD)

All tools return a **JSON string** (UTF-8). Errors surface as tool failures (`PermissionError`, `ValueError`, etc.).

| Entity | Create | Read | Update | Delete |
| ------ | ------ | ---- | ------ | ------ |
| **Audio** | `create_audio_upload`, `create_audio_import` | `list_audios`, `get_audio` | — | `delete_audio` |
| **Transcript** | — (via transcribe task / UI) | `list_transcripts`, `get_transcript` | `update_transcript` (`title`) | `delete_transcript` |
| **Summary** | `create_summary` (async task) | `list_summaries`, `get_summary` | `update_summary` (`title`, `body`) | `delete_summary` |
| **Skill** | `create_skill` | `list_skills`, `get_skill` | `update_skill` | `delete_skill` |

### Parameters

| Tool | Parameters | Scope |
| ---- | ----------- | ----- |
| `list_audios` | `include_hidden` (bool, default `false`) | `audio:read` |
| `get_audio` | `audio_id` | `audio:read` |
| `create_audio_upload` | `filename`, `content_base64` (standard or data-URL base64) | `audio:write` |
| `create_audio_import` | `url`, `transcribe` (bool), `skill_ids` optional | `tasks:write` |
| `delete_audio` | `audio_id` | `audio:write` |
| `list_transcripts` | `include_hidden` (bool, default `false`) | `transcripts:read` |
| `get_transcript` | `transcript_id` | `transcripts:read` |
| `update_transcript` | `transcript_id`, `title` | `transcripts:write` |
| `delete_transcript` | `transcript_id` | `transcripts:write` |
| `list_summaries` | `include_hidden` (bool, default `false`) | `summaries:read` |
| `get_summary` | `summary_id` | `summaries:read` |
| `create_summary` | `transcript_id`, `skill_ids` (non-empty list) | `tasks:write` |
| `update_summary` | `summary_id`, `title` optional, `body` optional | `summaries:write` |
| `delete_summary` | `summary_id` | `summaries:write` |
| `list_skills` | `scope` optional: `base`, `org`, `self`, `shared` | `skills:read` |
| `get_skill` | `skill_id` | `skills:read` |
| `create_skill` | `name`, `body`, `catalog` optional: `self` (default), `org`, `base` | `skills:write` |
| `update_skill` | `skill_id`, `name`, `body` | `skills:write` |
| `delete_skill` | `skill_id` | `skills:write` |

### Behavior notes

- **List tools** cap at **100** items and set `"truncated": true` when the library has more.
- **`create_audio_upload`**: `.wav`, `.mp3`, `.m4a` only (same validation as REST upload); max size follows org tariff.
- **`create_audio_import`**: same rules as `POST /tasks/import` (may enqueue import or capture); returns task JSON until audio exists.
- **`delete_audio`**: org admin only (same as `DELETE /audios/{id}`).
- **`get_transcript`** includes `utterances` and visible linked summary metadata (same as `GET /transcripts/{id}`).
- **`list_summaries`** / **`get_summary`** follow library read access; list entries omit body text until `get_summary`.
- **`create_summary`**: enqueues a **summarize** task (like `POST /tasks/summarize`); dispatcher runs asynchronously after the tool returns.
- **`update_transcript`** / **`delete_transcript`**: same rules as REST `PATCH` / `DELETE /transcripts/{id}` (delete: org admin only).
- **`list_skills`**: same catalog as `GET /skills` (`catalog`, `readonly` on each item).
- **`create_skill`** / **`update_skill`** / **`delete_skill`**: aligned with REST skills endpoints per catalog (`self`, `org`, `base`).

Implementation: `app/services/mcp_integration.py` (tool registration), `app/services/mcp_library.py` (business logic aligned with REST).

## Related

- [Auth & OAuth](auth.md)
- [Library](library.md)
- [Tasks](tasks.md)
- [Skills](skills.md)
