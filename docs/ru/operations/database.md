# База данных

## Движки

| Engine | Пример connection string |
| ------ | -------------------------- |
| SQLite (default) | `sqlite:///./data/hub.db` |
| PostgreSQL | `postgresql+psycopg://user:pass@host:5432/hub` |

Задаётся через `DATABASE_URL` в `.env`. Устаревший fallback при пустом значении: `SQLITE_PATH`.

**Смена URL создаёт пустую отдельную базу** — автоматической миграции между SQLite и PostgreSQL нет.

## Управление схемой

1. **SQLAlchemy models** — `app/models.py` (источник правды для новых ревизий)
2. **Alembic migrations** — `alembic/versions/`; применяются автоматически при старте через `init_database()` в `app/db.py` (`alembic upgrade head`)

Существующие базы, созданные до Alembic (через старый путь `ensure_schema()`), при первом старте определяются автоматически и получают `stamp head` перед upgrade.

Локальная разработка после изменения моделей:

```bash
./.venv/bin/alembic revision --autogenerate -m "description"
./.venv/bin/alembic upgrade head   # опционально; также выполнится при следующем старте
```

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
| `data_encryption_keys` | DEK (обёрнуты KEK) |
| `encryption_jobs` | Фоновые job перешифровки DEK |
| `password_reset_tokens` | Восстановление по email |

UUID хранятся как 36-символьные строки. Колонок soft-delete (`deleted_at`) нет.

## Зашифрованные колонки

Envelope encryption (`v1:{dek_id}:…`). Таблицы: `data_encryption_keys`, `encryption_jobs`, `instance_settings.active_dek_id`. Нужен валидный `HUB_SECRET` (и `HUB_SECRET_PREV` при ротации KEK). Старт падает, если KEK не unwrap'ит DEK. См. [Security](../architecture/security.md).

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
