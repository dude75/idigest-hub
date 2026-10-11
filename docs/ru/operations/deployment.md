# Развёртывание

Быстрый старт описан в [README](../../../README.ru.md) проекта. На этой странице — заметки для production.

## Требования к окружению

| Компонент | Версия |
| --------- | ------ |
| Python | 3.12 |
| Node.js | 22+ (только на этапе сборки) |
| Uvicorn workers | **1** всегда |

Несколько воркеров ломают in-memory rate limits и допущения блокировки dispatcher.

## Локальный запуск, похожий на production

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cd web && npm ci && npm run build && cd ..
cp .env.example .env   # fill secrets
./.venv/bin/python -m app.serve
```

SPA отдаётся из `web/dist` тем же процессом.

## Docker Compose

См. разделы README **Docker Compose**. Кратко:

- Образ работает от uid/gid **1001**
- Смонтируйте `./data:/data` для БД, логов и загрузок
- SQLite по умолчанию в контейнере: `sqlite:////data/hub.db`
- PostgreSQL опционально: `docker compose --profile pg up`

При необходимости исправьте права:

```bash
sudo chown -R 1001:1001 ./data
```

## HTTPS reverse proxy

Установите `COOKIE_SECURE=true` при работе через HTTPS, чтобы session cookies получали флаг `Secure`.

Hub слушает **только localhost** (`127.0.0.1:8080`); в `.env` задайте `TRUSTED_PROXIES=127.0.0.1,::1`, чтобы per-IP лимиты использовали реальные IP из заголовков прокси. Пустой `TRUSTED_PROXIES` — безопасный дефолт (заголовки игнорируются).

Полный пример site-конфига: [`deploy/nginx/idigest-hub.conf.example`](../../../deploy/nginx/idigest-hub.conf.example).

Минимальный location в nginx:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 1024m;
}
```

По умолчанию hub слушает HTTP. TLS на edge — на reverse proxy (см. пример nginx).

### TLS на hub (nginx → hub по LAN)

Если hub на отдельной машине и участок nginx → hub идёт по LAN, включите HTTPS на hub через `.env` (оба пути обязательны; самоподписанный PEM подходит):

```env
PORT=8443
SSL_CERTFILE=/data/certs/hub.crt
SSL_KEYFILE=/data/certs/hub.key
COOKIE_SECURE=true
TRUSTED_PROXIES=10.0.1.10
```

`TRUSTED_PROXIES` — IP nginx в LAN (не `127.0.0.1`, если прокси на другом хосте). Смонтируйте каталог с cert в контainer, напр. `./certs:/data/certs:ro`. Процесс запускается через `python -m app.serve` (Docker CMD по умолчанию).

На nginx:

```nginx
upstream idigest_hub {
    server 10.0.1.50:8443;
}

location / {
    proxy_pass https://idigest_hub;
    proxy_ssl_verify on;
    proxy_ssl_trusted_certificate /etc/ssl/certs/hub.crt;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

**Публичный URL** в Instance → Settings — адрес **внешнего** nginx (`https://hub.example.com`), не внутренний `:8443`.

### Заголовки безопасности (HSTS, CSP)

Полный пример nginx включает рекомендуемые заголовки в HTTPS-блоке:

| Заголовок | Назначение |
| --------- | ---------- |
| `Strict-Transport-Security` (HSTS) | Браузер запоминает, что сайт доступен только по HTTPS |
| `Content-Security-Policy` (CSP) | Ограничивает источники скриптов, стилей, медиа — снижает риск XSS |
| `X-Content-Type-Options` | Запрещает MIME-sniffing |
| `X-Frame-Options` | Защита от clickjacking (встраивание в iframe) |
| `Referrer-Policy` | Контроль заголовка `Referer` при переходах |

Hub сам эти заголовки не выставляет — настраивайте их на reverse proxy. Для SPA из `web/dist` базовая CSP в примере рассчитана на same-origin (`'self'`); SSO через редирект на IdP отдельных директив не требует.

- **Публичный HTTPS** — включайте HSTS и CSP из примера; после деплоя проверьте UI (логин, SSO, загрузка аудио, `/docs`).
- **Только внутренняя сеть** — рекомендация, не блокер; HSTS с `includeSubDomains` включайте только если все поддомены реально на HTTPS.
- **Проверка:** `curl -sI https://hub.example.com | grep -iE 'strict-transport|content-security'`

Если позже появятся внешние CDN или скрипты — расширьте `Content-Security-Policy`. Swagger UI (`/docs`) при строгой CSP может потребовать отдельного `location` с ослабленной политикой.

Задайте **Публичный URL** в Instance → Settings — внешний базовый адрес, по которому пользователи и Keycloak достигают хаба (напр. `https://hub.example.com`). Нужен для SSO org, ссылок сброса пароля, публичных ссылок на summary и MCP / OAuth 2.1 (`{public_url}/mcp`). См. [README — Публичный URL](../../../README.ru.md#публичный-url-instance-admin).

## Переменные окружения

Полная таблица в [README — `.env`](../../../README.ru.md#env). Критичные секреты:

- `HUB_SECRET` — KEK envelope encryption; backup `.env`; неверный секрет блокирует старт при наличии DEK/данных
- `HUB_SECRET_PREV` — прежний KEK только на время ротации; удалить после переобёртки DEK
- `SESSION_SECRET` — обязателен до `/setup`; смена разлогинивает всех; пустое значение блокирует старт при наличии sessions или API tokens
- `OPENAPI_ENABLED` — по умолчанию `false`; для `/docs`, `/redoc` и `/openapi.json` локально задайте `true`
- `INSTANCE_BOOTSTRAP_TOKEN` — только для одноразовой настройки
- `OAUTH_PROVIDER_ENABLED=true` — включить OAuth 2.1 хаба + MCP на `/mcp` (нужен Публичный URL)
- `OAUTH_SIGNING_KEY_PEM` — опциональный RSA PEM; иначе хаб пишет `{DATA_DIR}/oauth_signing_key.pem`

Изменения переменных окружения процесса требуют перезапуска.

## Персистентность данных

Под `{DATA_DIR}` (по умолчанию `./data`):

| Путь | Содержимое |
| ---- | ---------- |
| `hub.db` | SQLite database |
| `pg/` | Файлы PostgreSQL (compose profile) |
| `logs/` | Rotating `app.log` |
| `uploads/{audio_id}/` | Загруженное audio (**только local backend**) |
| `tmp/` | Временные файлы import/ffmpeg и worker S3 staging; `tmp/cache/yt-dlp` — кэш yt-dlp (можно удалить при остановленном hub, YouTube может снова потребовать cookies) |

Compose задаёт `TMPDIR=/data/tmp`, чтобы процесс не писал во writable layer контейнера.

При **`STORAGE_BACKEND=s3`** audio в настроенном bucket (server-side encryption). Hub скачивает во `{DATA_DIR}/tmp` при отправке на transcribe-воркер — API воркера не меняется.

**Стратегия резервного копирования:** остановите hub (опционально), скопируйте `./data` + содержимое bucket (если S3) и надёжно сохраните `.env`.

### Миграция audio между локальным диском и S3

Офлайн CLI копирует только объекты с префиксом `uploads/` (та же схема, что у hub: `{DATA_DIR}/uploads/{audio_id}/original{suffix}` ↔ `s3://{bucket}/uploads/...`). Берут **`DATA_DIR`** и **`S3_*`** из `.env`; **`STORAGE_BACKEND`** скрипты не меняют — выставьте его после копирования и перезапустите hub.

Перед массовой синхронизацией hub лучше остановить.

| Направление | Скрипт |
| ----------- | ------ |
| S3 → local | `scripts/storage_sync_s3_to_local.py` |
| local → S3 | `scripts/storage_sync_local_to_s3.py` |

Сначала **`--dry-run`** — список операций без записи. По умолчанию пропуск, если в назначении уже есть файл **того же размера**; **`--overwrite`** — принудительно. При upload в S3 учитываются **`S3_SSE`** / **`S3_SSE_KMS_KEY_ID`**, если заданы.

#### Docker Compose

Скрипты уже в образе hub (`/app/scripts/`). Compose монтирует **`./data:/data`**, задаёт **`DATA_DIR=/data`**; **`S3_*`** — из **`env_file: .env`**. Локальные uploads оказываются в **`./data/uploads`** на хосте.

Из каталога с `docker-compose.yml` и `.env`:

```bash
docker compose stop idigest-hub

docker compose run --rm --no-deps idigest-hub \
  python scripts/storage_sync_s3_to_local.py --dry-run

docker compose run --rm --no-deps idigest-hub \
  python scripts/storage_sync_s3_to_local.py
```

Для обратного направления замените имя на `storage_sync_local_to_s3.py`. Затем при необходимости обновите **`STORAGE_BACKEND`** в `.env` и `docker compose up -d idigest-hub`.

Предпочитайте **`docker compose run`**, пока основной hub остановлен — меньше риска параллельной записи. **`--no-deps`** не ждёт optional Postgres (sync storage БД не использует). Пересоберите образ (`docker compose build idigest-hub`), если он старше появления этих скриптов.

**S3 endpoint из контейнера:** `localhost` в **`S3_ENDPOINT`** — это контейнер, не хост. Для MinIO на хосте укажите URL, доступный из контейнера (например `http://host.docker.internal:9000` в Docker Desktop или IP хоста в Linux).

**Владелец файлов:** контейнер hub работает от **uid/gid 1001**. Sync через Compose создаёт файлы с владельцем 1001. При запуске скриптов на хосте убедитесь, что `./data/uploads` доступен на запись uid 1001 (`chown -R 1001:1001 ./data` при необходимости).

#### Установка без Docker (venv)

Из корня репозитория с venv проекта (нужен `boto3`):

```bash
./.venv/bin/python scripts/storage_sync_s3_to_local.py --dry-run
```

В `.env` задайте **`DATA_DIR=./data`**, чтобы пути совпадали с bind mount в Compose.

Скрипты **не обновляют** `storage_path` в БД. После смены бэкенда строки должны уже ссылаться на нужный вид (абсолютный путь для `local`, `s3://…` для `s3`). Типичный «чистый» переезд (пустой bucket перед S3 или пустое дерево uploads перед `local`) — sync + смена `STORAGE_BACKEND`; если инстанс уже писал пути под старый бэкенд, нужна отдельная правка БД.

См. также [Backend — operational CLI](../development/backend.md#operational-cli).

## Rate limiting

Настраивается в UI Instance → Settings (хранится в БД). Применяется в RAM — перезапуск обнуляет счётчики.

Auth-трафик: email + IP + global buckets. Bearer API: user + IP + global. Лимиты upload и создания task применяются **и** к Bearer, **и** к browser session.

`/api/v1/health` и статические ресурсы исключены.

## Пределы масштабирования

Текущая архитектура рассчитана на **single-node** развёртывание:

- Один цикл dispatcher
- In-memory rate limiter
- Локальная ФС или S3-compatible object storage для audio (`STORAGE_BACKEND`)

Горизонтальное масштабирование потребует общего store для rate limit и одного лидера dispatcher — S3 убирает необходимость shared filesystem для uploads, но multi-replica hub из коробки не поддерживается.

## Исследование API

OpenAPI **выключен по умолчанию** (`OPENAPI_ENABLED=false`). Для локального исследования API задайте `OPENAPI_ENABLED=true`:

- OpenAPI JSON: `GET /openapi.json`
- Swagger UI: `/docs` (Authorize с session cookie или Bearer token `idg_…`)

## Связанные страницы

- [Database](database.md)
- [Workers](workers.md)
- [Troubleshooting](troubleshooting.md)
