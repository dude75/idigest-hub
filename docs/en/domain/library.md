# Library: audio, transcripts, summaries

The **library** is the org-scoped store of user artifacts. Pipeline: **Audio → Transcript → Summary**.

## Audio

### Upload

`POST /audios` — multipart `file`

| Rule | Value |
| ---- | ----- |
| Allowed extensions | `.wav`, `.mp3`, `.m4a` |
| Max size | `min(tariff.max_upload_bytes, 1 GiB)` |
| Storage path | `{DATA_DIR}/uploads/{audio_id}/original{suffix}` |

Invalid extension → `invalid_file`. Over limit → `payload_too_large`.

### Endpoints

| Method | Path | Access |
| ------ | ---- | ------ |
| GET | `/audios` | List visible (see roles) |
| GET | `/audios/{id}` | Detail + transcript ids |
| GET | `/audios/{id}/file` | Download original |
| POST | `/audios/{id}/hide` | Owner |
| POST | `/audios/{id}/unhide` | Owner |
| DELETE | `/audios/{id}` | org_admin wipe |

Query `include_hidden=true` on list includes owner's hidden items.

### Transcribe eligibility

`can_transcribe` on audio detail is true when the file still exists on disk.

## Transcripts

Created by successful **transcribe tasks**, not uploaded directly.

- Utterances stored encrypted in DB as JSON array: `[{ "speaker": "...", "text": "..." }, ...]`
- `source_audio_id` links back (nullable after audio hard-delete via SET NULL)
- GET detail returns decrypted `utterances` + linked summaries

Hide/unhide/delete follow same pattern as audio (delete = org_admin wipe).

## Summaries

Created by successful **summarize tasks**.

| Field | Notes |
| ----- | ----- |
| `skill_ids` | JSON list of skill UUIDs used |
| `edited` | True if user PATCHed body |
| `source_transcript_id` | Provenance |

### Edit

`PATCH /summaries/{id}` — owner or org_admin can update `body`. Sets `edited=true`, re-encrypts body, audit log entry.

### Delete

Owner or org_admin — hard delete (not the same as org wipe endpoints for audio/transcript).

Summaries list always includes hidden items for owner filtering (no hide toggle in list API for summaries — hide badges still apply if set).

## Sharing

Share audio, transcript, summary, or personal skill with org colleagues:

```json
POST /shares
{
  "object_type": "transcript",
  "object_id": "...",
  "to_user_ids": ["...", "..."]
}
```

Recipients gain read access (and can use shared transcript in summarize if they have skill access). Response: `{ "ids": ["share_id", ...] }`.

Revoke: `DELETE /shares/{share_id}` — owner or recipient.

## List visibility algorithm

For org members (non-admin):

1. Include if owner
2. Include if shared to user
3. If owner and hidden (and not `include_hidden`), exclude

Org admins see all org rows regardless of share/hide.

## Hard delete cascade

`hard_delete_audio` / `hard_delete_transcript` / `hard_delete_summary` in `app/services/artifacts.py`:

- Removes files, DB rows, shares, hidden_items
- Running tasks referencing artifact may get `skip_persist` / `source_deleted`

Org admin DELETE on audio/transcript is destructive for the whole org view.

## Related pages

- [Tasks](tasks.md)
- [Skills](skills.md)
- [Library API](../api/library.md)
