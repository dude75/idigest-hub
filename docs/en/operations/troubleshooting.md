# Troubleshooting

Extended from [README — Typical errors](../../../README.md#typical-errors).

## Bootstrap and auth

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| `bootstrap_invalid` | Wrong/missing `INSTANCE_BOOTSTRAP_TOKEN` | Match `.env` token to `/setup` form |
| `setup_already_done` | Admin exists | Use login |
| `signup_disabled` | `allow_new_orgs=false` or no signup tariffs | Instance → Settings / Tariffs |
| `invalid_credentials` | Wrong password or disabled user | Reset or admin enable |
| `recovery_disabled` | SMTP not configured | Instance → Settings SMTP |
| `must_change_password` | Forced reset or TTL expired | Change password via UI/API |

## Balance and billing

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| `insufficient_balance` | Wallet ≤ 0 on metered tariff | Instance admin wallet top-up |
| Unexpected charge | Tariff snapshotted at task create | Check `usage_events` + task `snap_*` |
| API blocked | `api_enabled=false` on tariff | Change tariff or enable API |

## Tasks stuck

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| `queued` long time, `waiting_engine` | ASR/diarization loading | Wait for worker engines `loaded` |
| `queued` → `dispatch_timeout` | No enabled workers 1h | Register/fix workers |
| `running` forever | Worker hung | Check worker logs; restart worker |
| `pipeline_error` | Worker processing failed | Worker logs; retry new task |
| `source_deleted` | Audio removed mid-task | Re-upload |

## Workers

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| Health `_http: 0` | Network/unreachable `base_url` | Fix URL from hub network namespace |
| Engines not `loaded` | Model not ready on worker | Worker startup / GPU |
| Summarize never dispatches | `/ready` not 200 | Configure LLM on isummarize-worker |
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
