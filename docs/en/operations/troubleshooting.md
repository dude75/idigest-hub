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

## Health check

```bash
curl -s http://127.0.0.1:8080/api/v1/health
```

Returns version from `version.txt`.

## Related pages

- [Deployment](deployment.md)
- [Workers](workers.md)
- [Tasks](../domain/tasks.md)
