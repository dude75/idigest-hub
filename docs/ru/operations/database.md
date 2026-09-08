# База данных

## Движки

| Engine | Пример connection string |
| ------ | -------------------------- |
| SQLite (default) | `sqlite:///./data/hub.db` |
| PostgreSQL | `postgresql+psycopg://user:pass@host:5432/hub` |

Задаётся через `DATABASE_URL` в `.env`. Устаревший fallback при пустом значении: `SQLITE_PATH`.

**Смена URL создаёт пустую отдельную базу** — автоматической миграции между SQLite и PostgreSQL нет.

## Управление схемой

1. **SQLAlchemy models** — `app/models.py`; `Base.metadata.create_all()` при старте
2. **Alembic migrations** — `alembic/versions/` для инкрементальных изменений; `ensure_schema()` в `app/db.py` применяет лёгкие патчи

Production workflow:

```bash
./.venv/bin/alembic upgrade head
```

Всегда выполняйте миграции перед запуском новой версии.

## Основные таблицы

| Table | Назначение |
| ----- | ---------- |
| `instance_settings` | Singleton row (id=1): bootstrap, SMTP, rate limits, ASR models |
| `users` | Учётные записи |
| `organizations` | Tenants + balance |
| `memberships` | user ↔ org + role |
| `sessions` | Cookie sessions + impersonation |
| `api_tokens` | Bearer tokens (hashed) |
| `tariffs` | Тарифные планы |
| `worker_nodes` | Реестр внешних воркеров |
| `tasks` | Очередь задач hub |
| `audios` | Метаданные загрузок |
| `transcripts` | Encrypted utterances |
| `summaries` | Encrypted bodies |
| `skills` | Шаблоны промптов |
| `shares` / `hidden_items` | Sharing и per-user hide |
| `usage_events` | Billing ledger |
| `audit_log` | Действия админов |
| `password_reset_tokens` | Восстановление по email |

UUID хранятся как 36-символьные строки. Колонок soft-delete (`deleted_at`) нет.

## Зашифрованные колонки

Требуют валидный `HUB_SECRET`. См. [Security](../architecture/security.md).

## Заметки по SQLite

- Single-writer; подходит под дизайн с одним Uvicorn worker
- Путь к файлу БД относительно CWD процесса, если в URL не абсолютный
- Dispatcher часто делает commit — используйте SSD для `./data`

## Заметки по PostgreSQL

Docker Compose profile `pg` хранит данные в `./data/pg` (uid **999** внутри PG container).

Hub container по-прежнему использует uid **1001** для uploads/logs.

## Retention job

Dispatcher вызывает `purge_expired_audio()` на каждом tick — удаляет audio после org tariff `audio_retention_days`, если на него не ссылаются активные tasks.

## Связанные страницы

- [Deployment](deployment.md)
- [Billing](../domain/billing.md)
