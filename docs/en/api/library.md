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
| GET | `/summaries` | List |
| GET | `/summaries/{id}` | Detail with `body` |
| GET | `/summaries/{id}/export?format=md\|txt` | Download summary |
| PATCH | `/summaries/{id}` | `{ "body": "..." }` and/or `{ "title": "..." }` — owner or org_admin |
| DELETE | `/summaries/{id}` | Owner or org_admin |

## Shares

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

## Related pages

- [Library domain](../domain/library.md)
- [Tasks API](tasks.md)
