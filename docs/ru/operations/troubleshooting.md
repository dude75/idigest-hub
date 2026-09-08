# Устранение неполадок

Расширение раздела [README — Typical errors](../../../README.ru.md#типичные-ошибки).

## Bootstrap и auth

| Симптом | Причина | Решение |
| ------- | ------- | ------- |
| `bootstrap_invalid` | Неверный/отсутствующий `INSTANCE_BOOTSTRAP_TOKEN` | Сопоставьте token из `.env` с формой `/setup` |
| `setup_already_done` | Админ уже существует | Используйте login |
| `signup_disabled` | `allow_new_orgs=false` или нет signup tariffs | Instance → Settings / Tariffs |
| `invalid_credentials` | Неверный пароль или отключённый user | Reset или enable через admin |
| `recovery_disabled` | SMTP не настроен | Instance → Settings SMTP |
| `must_change_password` | Принудительный reset или истёк TTL | Смените пароль через UI/API |

## Balance и billing

| Симптом | Причина | Решение |
| ------- | ------- | ------- |
| `insufficient_balance` | Wallet ≤ 0 на metered tariff | Пополнение wallet через instance admin |
| Unexpected charge | Tariff snapshotted при создании task | Проверьте `usage_events` + task `snap_*` |
| API blocked | `api_enabled=false` на tariff | Смените tariff или включите API |

## Задачи зависли

| Симптом | Причина | Решение |
| ------- | ------- | ------- |
| `queued` долго, `waiting_engine` | ASR/diarization загружается | Дождитесь worker engines `loaded` |
| `queued` → `dispatch_timeout` | Нет enabled workers 1h | Зарегистрируйте/исправьте workers |
| `running` forever | Worker завис | Проверьте worker logs; перезапустите worker |
| `pipeline_error` | Worker processing failed | Worker logs; создайте новую task |
| `source_deleted` | Audio удалён во время task | Re-upload |

## Workers

| Симптом | Причина | Решение |
| ------- | ------- | ------- |
| Health `_http: 0` | Network/unreachable `base_url` | Исправьте URL из network namespace hub |
| Engines not `loaded` | Model не готов на worker | Worker startup / GPU |
| Summarize never dispatches | `/ready` not 200 | Настройте LLM на isummarize-worker |
| 404 redispatch loop | Worker перезапущен | Обычно self-heals; проверьте стабильность worker |

## Data и encryption

| Симптом | Причина | Решение |
| ------- | ------- | ------- |
| Decrypt errors after deploy | `HUB_SECRET` изменён | Восстановите старый secret или заново введите worker tokens |
| Transcripts empty/garbled | DB corruption или wrong key | Восстановите backup |
| Upload `Permission denied` | `./data` не writable для uid 1001 | `chown -R 1001:1001 ./data` |

## Rate limits

| Симптом | Причина | Решение |
| ------- | ------- | ------- |
| `rate_limited` + `Retry-After` | Bucket exceeded | Подождите или поднимите limits в Instance → Settings |
| All users share one IP | Reverse proxy без real IP | Expected; используйте per-email/user limits |

## Логи

Application logs: `{LOG_DIR}/app.log` (rotating). Отключить: `LOG_ENABLED=false`.

Dispatcher логирует сбои воркеров на INFO: `worker health failed`, `worker poll network error`, `worker 404 redispatch`.

## Health check

```bash
curl -s http://127.0.0.1:8080/api/v1/health
```

Возвращает version из `version.txt`.

## Связанные страницы

- [Deployment](deployment.md)
- [Workers](workers.md)
- [Tasks](../domain/tasks.md)
