# Billing and tariffs

Money is stored as `Numeric(12,2)`; charges are **floored to cents** (`app/money.py`).

## Tariff fields

| Field | Meaning |
| ----- | ------- |
| `unlimited` | If true, balance never decrements; usage still logged with `unlimited_skip=true` |
| `available_on_signup` | Shown on signup and allowed for org self-service tariff change |
| `archived_at` | Non-null = archived; hidden from signup, cannot assign to new orgs |
| `price_per_audio_sec` | Transcribe: duration × rate |
| `price_per_summarize_job` | Flat fee per successful summarize |
| `price_per_1k_summary_chars` | Per 1000 characters of **output** summary (rounded up) |
| `signup_credit` | Initial wallet on signup (ignored when unlimited) |
| `max_upload_bytes` | Upload cap (capped globally at 1 GiB) |
| `audio_retention_days` | `0` = keep forever; else purge job deletes old audio |
| `api_enabled` | If false, Bearer tokens rejected with `api_disabled` |

Default tariff seeded at setup: name `"Default"`, `unlimited=true`, `available_on_signup=true`.

## Wallet

- One balance per organization
- **Instance admin** adjusts via `POST /instance/orgs/{org_id}/wallet` with `delta` (string decimal, e.g. `"10.00"` or `"-5"`)
- Before accepting a new task (non-unlimited): `balance` must be **> 0** or API returns `insufficient_balance` (HTTP 429)

Charges apply **only on successful task completion**, once per task (`task.billed` guard).

## Tariff snapshot on task

When a task is created, current tariff limits/prices are copied to the task row:

```
snap_unlimited
snap_price_per_audio_sec
snap_price_per_summarize_job
snap_price_per_1k_summary_chars
snap_max_upload_bytes
snap_asr_model          # transcribe only, from instance settings
snap_diarization_model  # transcribe only
```

Transcribe uses instance ASR/diarization settings at creation time; summarize snapshots do not include models.

## Pricing formulas

### Transcribe

```
amount = floor_to_cents(audio_duration_sec × snap_price_per_audio_sec)
```

Duration comes from worker result meta `audio_duration_sec`. Also backfills `audios.duration_sec` if missing.

### Summarize

```
job = floor_to_cents(snap_price_per_summarize_job)
units = ceil(len(summary_text) / 1000)   # 0 if empty
text = floor_to_cents(units × snap_price_per_1k_summary_chars)
amount = job + text
```

## Usage events

Each successful charge creates a `usage_events` row:

| Field | Content |
| ----- | ------- |
| `kind` | `transcribe` or `summarize` |
| `amount` | Charged amount |
| `audio_sec` | Transcribe duration |
| `summary_chars` | Output length for summarize |
| `unlimited_skip` | True if snap was unlimited |

Org stats and `/org` usage totals aggregate these rows.

## API access gating

`org.tariff.api_enabled` must be true for:

- Bearer authentication
- Creating API tokens (tokens list shows `blocked_by_tariff` when disabled)

Browser sessions are unaffected.

## Audio retention billing interaction

Retention purge (`purge_expired_audio`) deletes audio files past `audio_retention_days` when no queued/running task references them. Transcripts/summaries remain unless explicitly wiped.

## Related pages

- [Organizations](organizations.md)
- [Tasks](tasks.md)
- [Instance API](../api/instance.md)
