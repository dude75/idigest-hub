# Library API

Auth required. Org membership required for all endpoints.

## Audio

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/audios` | Multipart upload (`file` field) |
| GET | `/audios?include_hidden=false` | List |
| GET | `/audios/{id}` | Detail + transcript list + `can_transcribe` |
| GET | `/audios/{id}/file` | Stream audio (inline playback) |
| GET | `/audios/{id}/file?download=true` | Download original file |
| POST | `/audios/{id}/hide` | Owner hide |
| POST | `/audios/{id}/unhide` | Owner unhide |
| DELETE | `/audios/{id}` | org_admin hard delete |

List/detail items include share badges: `share_kind`, `shared_with`, `shared_by`, `hidden`, `owner_email`.

## Transcripts

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/transcripts?include_hidden=false` | List |
| GET | `/transcripts/{id}` | Detail with `utterances` array |
| PATCH | `/transcripts/{id}` | `{ "title": "..." }` — owner or org_admin |
| GET | `/transcripts/{id}/export?format=txt\|json` | Download transcript |
| POST | `/transcripts/{id}/hide` | Owner |
| POST | `/transcripts/{id}/unhide` | Owner |
| DELETE | `/transcripts/{id}` | org_admin wipe |

Utterance shape:

```json
{
  "speaker": "SPEAKER_00",
  "text": "Hello world"
}
```

## Summaries

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/summaries?include_hidden=false` | List |
| GET | `/summaries/{id}` | Detail with `body` |
| GET | `/summaries/{id}/export?format=md\|txt` | Download summary (markdown fences stripped) |
| PATCH | `/summaries/{id}` | `{ "body": "..." }` and/or `{ "title": "..." }` — owner or org_admin |
| POST | `/summaries/{id}/hide` | Owner |
| POST | `/summaries/{id}/unhide` | Owner |
| DELETE | `/summaries/{id}` | Owner or org_admin |

### Summary public links

Share a read-only guest URL for a summary (requires Public URL + org `allow_public_links`).

| Method | Path | Access |
| ------ | ---- | ------ |
| GET | `/summaries/{id}/public-link` | Owner or org_admin |
| POST | `/summaries/{id}/public-link` | Owner only |
| DELETE | `/summaries/{id}/public-link` | Owner or org_admin |

**POST body:**

```json
{
  "expires_in_days": 7,
  "pin": "1234"
}
```

- `expires_in_days`: optional; omit or `null` for no expiry; `<= 0` invalid
- `pin`: optional 4–6 digit PIN; omit for open access

Response `{ "link": { "id", "summary_id", "url", "expires_at", "pin_required", "created_at", "revoked" } }`. Creating again replaces the previous link (new token).

Errors: `public_base_url_missing` (400), `public_links_disabled` (403).

Guest access (no auth): [public.md](public.md).

## Shares

### GET `/shares?object_type=...&object_id=...`

Owner only. Lists outgoing shares: `{ "items": [{ "id", "to_user_id", "to_email", "created_at" }, ...] }`.

### POST `/shares`

```json
{
  "object_type": "audio|transcript|summary|skill",
  "object_id": "uuid",
  "to_user_ids": ["uuid", "uuid"]
}
```

Returns `{ "ids": ["share_id", ...] }`. Skips self and unknown org members.

### DELETE `/shares/{share_id}`

Owner or recipient may revoke.

MCP equivalents (OAuth JWT, same access rules): [MCP tools](mcp.md) — `list_audios` / `get_audio` / `create_audio_upload` / `delete_audio`, `list_transcripts` / `get_transcript` / `update_transcript` / `delete_transcript`, `list_summaries` / `get_summary` / `update_summary` / `delete_summary`.

## Related pages

- [Library domain](../domain/library.md)
- [Tasks API](tasks.md)
- [MCP tools](mcp.md)
