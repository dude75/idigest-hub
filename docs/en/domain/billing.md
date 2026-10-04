# Billing and tariffs

Money is stored as `Numeric(12,2)`; charges are **floored to cents** (`app/money.py`). If the raw amount is positive but floors to `0.00`, the charge is **at least 0.01** (`usage_charge_amount`).

## Tariff fields

| Field | Meaning |
| ----- | ------- |
| `unlimited` | If true, balance never decrements; usage still logged with `unlimited_skip=true` |
| `available_on_signup` | Shown on signup and allowed for org self-service tariff change |
| `archived_at` | Non-null = archived; hidden from signup, cannot assign to new orgs |
| `price_per_audio_sec` | Transcribe: duration × rate |
| `price_per_1k_summary_chars` | Summarize: per 1000 characters of **output** summary (rounded up) |
| `signup_credit` | Initial wallet on signup (ignored when unlimited) |
| `max_upload_bytes` | Upload cap (capped globally at 1 GiB) |
| `audio_retention_days` | `0` = keep forever; else purge job deletes old audio |
| `api_enabled` | If false, Bearer tokens rejected with `api_disabled` |

Default tariff seeded at setup: name `"Default"`, `unlimited=true`, `available_on_signup=true`.

## Deleting tariffs

Instance admin removes tariffs from **Instance → Tariffs** (or `DELETE /tariffs/{id}`). The UI loads `GET /tariffs/{id}/delete-impact` first (same pattern as worker delete):

- **No orgs** — delete succeeds if at least one other tariff remains.
- **Orgs still on the tariff** — choose a **non-archived** replacement in the impact modal (or send `remediation.tariff_id` on DELETE). All affected orgs are reassigned, then the tariff row is removed. Without remediation → `tariff_in_use` (409).
- **Last tariff in the instance** — blocked (`last_tariff`, 409); create or clone another tariff first.

Archiving hides a tariff from signup and org self-service but does not move existing orgs. Clone (`POST /tariffs/{id}/clone`) copies settings into a new active tariff.

## Wallet

- One balance per organization
- **Instance admin** adjusts via `POST /orgs/{org_id}/wallet` with `delta` (string decimal, e.g. `"10.00"` or `"-5"`)
- **Ledger** — `GET /orgs/{org_id}/ledger` merges usage charges and wallet top-ups for auditing (Instance UI modal with filters)
- Before accepting a new task (non-unlimited): `balance` must be **> 0** or API returns `insufficient_balance` (HTTP 429)

Charges apply **only on successful task completion**, once per task (`task.billed` guard).

## Tariff snapshot on task

When a task is created, current tariff limits/prices are copied to the task row:

```
snap_unlimited
snap_price_per_audio_sec
snap_price_per_1k_summary_chars
snap_max_upload_bytes
snap_asr_model          # transcribe only, user override or instance default
snap_diarization_model  # transcribe only, user override or instance default
snap_summarize_model    # summarize only, user override or instance default
```

Transcribe and summarize resolve models at creation (user profile → instance settings) and snapshot them.

## Pricing formulas

### Transcribe

```
amount = usage_charge_amount(audio_duration_sec × snap_price_per_audio_sec)
```

Duration comes from worker result meta `audio_duration_sec`. Also backfills `audios.duration_sec` if missing.

### Summarize

```
units = ceil(len(summary_text) / 1000)   # 0 if empty
amount = usage_charge_amount(units × snap_price_per_1k_summary_chars)
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

When a **member** deletes their account but the organization remains, usage rows for that org are **kept** (amounts and dates); `user_id` and `task_id` are cleared so org billing totals stay aligned with wallet charges. Deleting the **whole organization** removes all its usage events.

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
