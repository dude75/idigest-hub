# Troubleshooting

Extended from [README — Typical errors](../../../README.md#typical-errors).

## Bootstrap and auth

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| `bootstrap_invalid` | Wrong/missing `INSTANCE_BOOTSTRAP_TOKEN` | Match `.env` token to `/setup` form |
| `setup_already_done` | Admin exists | Use login |
| `signup_disabled` | `allow_new_orgs=false` or no signup tariffs | Instance → Settings / Tariffs |
| `invalid_credentials` | Wrong password or disabled user | Reset or admin enable |
| Forgot **instance admin** password | No other admin, SMTP recovery unavailable | Break-glass on host with `.env` + DB: `python scripts/reset_instance_admin_password.py --confirm` (see `--email`, `--clear-mfa`, `--enable`) |
| `recovery_disabled` | SMTP not configured | Instance → Settings SMTP |
| `must_change_password` | Forced reset or TTL expired | Change password via UI/API |

## Balance and billing

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| `insufficient_balance` | Wallet ≤ 0 on metered tariff | Instance admin wallet top-up |
| Unexpected charge | Tariff snapshotted at task create | Check `usage_events` + task `snap_*` |
| API blocked | `api_enabled=false` on tariff | Change tariff or enable API |
| `tariff_in_use` on DELETE | Orgs still reference the tariff | Instance → Tariffs: use delete impact modal and move orgs (`remediation.tariff_id`), or reassign via **Organizations** first |
| `last_tariff` on DELETE | Only one tariff left | Clone or create another tariff before deleting |

## Tasks stuck

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| `queued` long time, `waiting_engine` | No worker with full model set, or engines loading | Ensure one transcribe node offers both snapshotted ASR and diarization (if any) and reports them `loaded` in `/health` |
| `queued` → `dispatch_timeout` | No enabled workers 1h | Register/fix workers |
| `running` forever | Worker hung | Check worker logs; restart worker |
| `pipeline_error` | Worker processing failed | Worker logs; retry new task |
| `source_deleted` | Audio removed mid-task | Re-upload |

## Workers

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| Health `_http: 0` | Network/unreachable `base_url` | Fix URL from hub network namespace |
| Engines not `loaded` | Model not ready on worker | Worker startup / GPU |
| Summarize never dispatches | `/ready` not 200 | Configure LLM on [isummarize-worker](https://github.com/dude75/isummarize-worker) |
| Summarize stays `queued`, `no_matching_worker` | Snapshotted LLM name is not offered by any enabled summarize worker | Instance → Settings or Profile: pick a model a live worker reports; or remediate when deleting the last worker for that model |
| **`capture_no_worker`** on POST import/capture | Chosen capture worker not dispatch-ready at enqueue (connector not `loaded`, `workers.available` is 0, bad token / health) | Fix worker health and hub token; Instance → Settings: capture + connector; Jitsi org host map. Hub does **not** queue capture until the worker returns — fix worker, then submit again |
| Capture task errors immediately with `capture_no_worker` after create | Worker became unavailable before background start (race) | Same as above; rare if capacity was taken between enqueue and start |
| 404 redispatch loop | Worker restarted | Usually self-heals; check worker stability |

## Data and encryption

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| Process exits on start: `FATAL: HUB_SECRET…` | Empty/wrong KEK with existing DEKs or ciphertext | Restore correct `HUB_SECRET`; during KEK rotation set `HUB_SECRET_PREV` to old value and restart |
| `deks_pending_rewrap` > 0 in Security → Encryption | KEK rotation incomplete | Keep `HUB_SECRET` + `HUB_SECRET_PREV`, restart until pending = 0 |
| Re-encrypt job `failed` | Background job error (see UI) | Fix cause, retry **Re-encrypt and remove old DEKs** |
| Decrypt errors at runtime | Rare after successful startup | Check active DEK in Security → Encryption; restore backup |
| Transcripts empty/garbled | DB corruption | Restore backup |
| Upload `Permission denied` | `./data` not writable by uid 1001 | `chown -R 1001:1001 ./data` |

## Rate limits

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| `rate_limited` + `Retry-After` | Bucket exceeded | Wait or raise limits in Instance → Settings |
| All users share one IP | Reverse proxy without real IP | Expected; use per-email/user limits |

## Logs

Application logs: `{LOG_DIR}/app.log` (rotating). Disable with `LOG_ENABLED=false`.

Dispatcher logs worker failures at INFO: `worker health failed`, `worker poll network error`, `worker 404 redispatch`.

## Telegram bot

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| Bot silent, logs `telegram getMe failed` / `socksio` | SOCKS proxy without optional dependency | Rebuild image with `httpx2[socks]`; `pip show socksio` in container |
| `getWebhookInfo` → `Connection timed out`, pending updates grow | Telegram cannot reach `{public_url}` on **443** (perimeter firewall, not hub) | Fix reverse proxy path to hub; or **Instance → Telegram** → disable **Deliver updates via webhook** (long polling; Public URL unchanged) |
| Webhook POST returns **403** | Wrong/missing `X-Telegram-Bot-Api-Secret-Token` | Secret is in DB (`telegram_webhook_secret`); re-save Telegram settings or restart hub to re-register |
| **Check connection** OK, bot still silent on webhook | Hub stuck in webhook wait mode | Save Telegram settings again or `docker compose restart idigest-hub` after switching to long polling |
| Duplicate commands, missed updates, `getUpdates` errors | Multiple processes on long polling (`workers > 1` or several replicas) | Single process / `workers: 1`, or enable **Deliver updates via webhook** |
| Bot goes silent after an inline button choice | Next request hit another replica (in-process bot state) | Stay single-node for now; with multiple replicas use sticky sessions to one replica, or webhook and accept the limitation |

Diagnostics on the hub host (use `import app.db as hub_db`, then `hub_db.get_engine()` before `SessionLocal()`):

```bash
docker compose exec idigest-hub python -c "
import asyncio, app.db as hub_db
from app.deps import get_instance_settings
from app.services.telegram_identity import bot_token
from app.services.telegram_api import get_me, get_webhook_info
hub_db.get_engine()
with hub_db.SessionLocal() as db:
    s = get_instance_settings(db)
    t = bot_token(s, db)
    print('use_webhook', s.telegram_use_webhook, 'public_base_url', s.public_base_url)
    print('getMe', asyncio.run(get_me(t, settings=s, db=db)))
    print('webhook', asyncio.run(get_webhook_info(t, settings=s, db=db)))
"
```

Nginx must proxy **all** of `/` (including `/api/v1/integrations/telegram/webhook`) to the hub. For HTTPS upstream to a self-signed hub, set `proxy_ssl_verify off`. See [README — Telegram bot](../../../README.md#telegram-bot-instance-admin).

## Health check

```bash
curl -s http://127.0.0.1:8080/api/v1/health
```

Returns version from `version.txt`.

## Related pages

- [Deployment](deployment.md)
- [Workers](workers.md)
- [Tasks](../domain/tasks.md)
