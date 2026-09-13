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

Задайте **Публичный URL** в Instance → Settings — внешний базовый адрес, по которому пользователи и Keycloak достигают хаба (напр. `https://hub.example.com`). Нужен для SSO org, ссылок сброса пароля и корректных OAuth redirect URI. См. [README — Публичный URL](../../../README.ru.md#публичный-url-instance-admin).

## Переменные окружения

Полная таблица в [README — `.env`](../../../README.ru.md#env). Критичные секреты:

- `HUB_SECRET` — KEK envelope encryption; backup `.env`; неверный секрет блокирует старт при наличии DEK/данных
- `HUB_SECRET_PREV` — прежний KEK только на время ротации; удалить после переобёртки DEK
- `SESSION_SECRET` — смена разлогинивает всех
- `INSTANCE_BOOTSTRAP_TOKEN` — только для одноразовой настройки

Изменения переменных окружения процесса требуют перезапуска.

## Персистентность данных

Под `{DATA_DIR}` (по умолчанию `./data`):

| Путь | Содержимое |
| ---- | ---------- |
| `hub.db` | SQLite database |
| `pg/` | Файлы PostgreSQL (compose profile) |
| `logs/` | Rotating `app.log` |
| `uploads/{audio_id}/` | Загруженное audio (**только local backend**) |

При **`STORAGE_BACKEND=s3`** audio в настроенном bucket (server-side encryption). Hub скачивает во временный файл при отправке на transcribe-воркер — API воркера не меняется.

**Стратегия резервного копирования:** остановите hub (опционально), скопируйте `./data` + содержимое bucket (если S3) и надёжно сохраните `.env`.

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

- OpenAPI JSON: `GET /openapi.json`
- Swagger UI: `/docs` (Authorize с session cookie или Bearer token `idg_…`)

## Связанные страницы

- [Database](database.md)
- [Workers](workers.md)
- [Troubleshooting](troubleshooting.md)
