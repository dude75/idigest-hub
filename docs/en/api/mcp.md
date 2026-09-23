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

| Scope | MCP tools | REST API (Bearer JWT) |
| ----- | --------- | --------------------- |
| `transcripts:read` | `list_transcriptions`, `get_transcript` | `GET /transcripts`, `GET /transcripts/{id}` |
| `summaries:read` | `list_summaries`, `get_summary` | — (REST uses session/PAT; no scope check) |
| `summaries:write` | `delete_summary` | — |
| `skills:read` | `list_skills` | — |
| `skills:write` | `update_skill` | — |
| `tasks:write` | `summarize_transcript` | — |

Scope checks apply when `via_oauth_token` is true (OAuth JWT). Session cookies and PAT on REST are governed by normal role rules, not these scopes.

Example authorize scope string for full library automation:

```
transcripts:read summaries:read summaries:write skills:read skills:write tasks:write
```

## Tools

All tools return a **JSON string** (UTF-8). Errors surface as tool failures (`PermissionError`, `ValueError`, etc.).

| Tool | Parameters | Required scope |
| ---- | ----------- | -------------- |
| `list_transcriptions` | `include_hidden` (bool, default `false`) | `transcripts:read` |
| `get_transcript` | `transcript_id` | `transcripts:read` |
| `list_summaries` | `include_hidden` (bool, default `false`) | `summaries:read` |
| `get_summary` | `summary_id` | `summaries:read` |
| `delete_summary` | `summary_id` | `summaries:write` |
| `list_skills` | `scope` optional: `base`, `org`, `self`, `shared` | `skills:read` |
| `update_skill` | `skill_id`, `name`, `body` | `skills:write` |
| `summarize_transcript` | `transcript_id`, `skill_ids` (non-empty list) | `tasks:write` |

### Behavior notes

- **List tools** cap at **100** items and set `"truncated": true` when the library has more.
- **`get_transcript`** includes `utterances` and visible linked summary metadata (same visibility rules as `GET /transcripts/{id}`).
- **`list_summaries`** / **`get_summary`** follow library read access; list entries omit body text until `get_summary`.
- **`delete_summary`**: owner or org admin for summaries in the org (same as `DELETE /summaries/{id}`).
- **`list_skills`**: same catalog as `GET /skills` (`catalog`, `readonly` flags on each item).
- **`update_skill`**: personal skills (owner), org skills (org admin), base skills (instance admin). Shared/incoming skills are not updatable.
- **`summarize_transcript`**: enqueues a **summarize** task (like `POST /tasks/summarize`), returns task JSON (`id`, `status`, …). Requires balance/tariff rules and at least one valid `skill_id`. Dispatcher runs asynchronously after the tool returns.

Implementation: `app/services/mcp_integration.py` (tool registration), `app/services/mcp_library.py` (business logic aligned with REST).

## Related

- [Auth & OAuth](auth.md)
- [Library](library.md)
- [Tasks](tasks.md)
- [Skills](skills.md)
