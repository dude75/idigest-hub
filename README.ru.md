# idigest-hub

Локальный (on-premise) **multi-tenant control plane** над [itranscribe-worker](#подключить-воркеры) и [isummarize-worker](#подключить-воркеры). Пользователи ходят только в хаб. Хаб владеет органами, ролями, кошельками, скилами, артефактами и своей очередью задач (`POST` → **202** + `task_id` → poll). Воркеры остаются внешними.

**Язык:** [English](README.md) · [Русский](README.ru.md)

## Что это

- Signup по умолчанию **открыт**. Из коробки — SQLite (`./data/hub.db`).
- Один `instance_admin` создаётся при первом запуске (`/setup`). Остальные живут в организации (`org_admin` / `org_member`).
- Пользователи не видят URL и API-токены воркеров. Instance admin подключает воркеры в UI (базовый URL + bearer-токен).
- FastAPI отдаёт собранную SPA с того же origin (`web/dist`). Session cookie — HttpOnly + `SameSite=Lax`, без CORS.
- HTTP-порт по умолчанию **8080**, чтобы не пересечься с воркерами на `8000`.
- Compose поднимает **только хаб** и volume `./data`. Воркеров в этот стек не класть.

## Требования

- Python **3.12**
- Виртуальное окружение `.venv` (только `./.venv/bin/python` и `./.venv/bin/pip`)
- **Node.js** (22+) для сборки SPA в `web/`
- Диск под `./data` для SQLite, логов и загрузок аудио (в git не коммитится)

## Установка и запуск

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements.txt

cd web
npm ci
npm run build
cd ..
```

Скопируйте `.env.example` → `.env` и заполните секреты (см. [`.env`](#env)). Файл не коммитить. Затем:

```bash
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --workers 1
```

Всегда **uvicorn** `--workers 1`. В проде SPA отдаётся из `web/dist` этим же процессом.

Для разработки UI оставьте API на `8080` и запустите Vite (проксирует `/api` на хаб):

```bash
cd web
npm install
npm run dev
```

Дальше откройте URL Vite (обычно `http://127.0.0.1:5173`).

Проверка:

```bash
curl -s http://127.0.0.1:8080/api/v1/health
```

В JSON — `version` (как в `version.txt`). Docker: [Docker Compose](#docker-compose).

## Первичная настройка

Пока bootstrap не сделан, откройте **`/setup`** в UI (`http://127.0.0.1:8080/setup`) и создайте instance admin с `INSTANCE_BOOTSTRAP_TOKEN` из `.env`.

Тот же вызов по HTTP:

```bash
curl -sS -X POST http://127.0.0.1:8080/api/v1/setup \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"choose-a-long-password","bootstrap_token":"'"$INSTANCE_BOOTSTRAP_TOKEN"'","locale":"ru"}'
```

Можно выполнить **один раз**. Повтор — HTTP **409** `setup_already_done`. Второго instance admin нет.

## `.env`

Имена переменных — в `.env`. **Реальные токены не класть в git и не копировать в README.** Смена значения требует перезапуска процесса.

| Переменная                   | Смысл                                                                                                                                                            |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `HUB_SECRET`                 | Материал ключа шифрования at-rest (см. ниже). Пустой — encrypt/decrypt падает.                                                                                   |
| `INSTANCE_BOOTSTRAP_TOKEN`   | Одноразовый секрет для `POST /api/v1/setup` / UI `/setup`. Пустой или неверный — `bootstrap_invalid`.                                                            |
| `SESSION_SECRET`             | Перец для хешей сессий и API-токенов. Смена инвалидирует уже выданные cookie и токены.                                                                           |
| `HOST`                       | Интерфейс (`127.0.0.1` локально; в Docker — `0.0.0.0`).                                                                                                          |
| `PORT`                       | HTTP-порт (по умолчанию `8080`).                                                                                                                                 |
| `DATA_DIR`                   | Корень персистентных данных (по умолчанию `./data`): SQLite, логи, загрузки `{DATA_DIR}/uploads/{audio_id}/`.                                                    |
| `SQLITE_PATH`                | БД хаба (по умолчанию `./data/hub.db`). Токены воркеров, транскрипты и саммари на диске зашифрованы (см. ниже).                                                   |
| `LOG_DIR`                    | Каталог прикладных логов (по умолчанию `./data/logs`).                                                                                                           |
| `LOG_ENABLED`                | Прикладной лог-файл + app-logger. По умолчанию `true`. `false` / `0` / `no` — выкл.                                                                              |
| `LOG_MAX_BYTES`              | Ротация `app.log` при превышении размера в байтах. По умолчанию `5242880` (5 MiB).                                                                               |
| `LOG_BACKUP_COUNT`           | Сколько архивов хранить (`app.log.1` … `app.log.N`). По умолчанию `5`.                                                                                           |
| `COOKIE_SECURE`              | Флаг `Secure` у session cookie. По умолчанию `false` (локальный HTTP). За HTTPS ставьте `true`.                                                                  |

Всё, что должно пережить рестарт, лежит в `./data` (`hub.db`, логи **и загрузки** `{DATA_DIR}/uploads/{audio_id}/`). В Docker монтируйте этот каталог. Контейнер Compose пишет в него от uid/gid **1001** (см. [Docker Compose](#docker-compose)).

`api_token` воркеров, JSON транскриптов, тела саммари и SMTP-пароль в SQLite хранятся в Fernet (AES-128-CBC + HMAC). Ключ — `SHA-256(HUB_SECRET)`, не сырой секрет — та же идея, что `API_TOKEN` у воркеров. API по-прежнему отдаёт открытый текст авторизованным клиентам. Аудио на диске в этой версии **не** шифруется. Это защита только от утечки `hub.db` без `.env`.

**Смена `HUB_SECRET` делает уже зашифрованные строки нечитаемыми** (токены воркеров, транскрипты, саммари, SMTP-пароль). Автоматической перешифровки нет. Задайте секрет один раз и храните запасную копию `.env`. То же предупреждение, что у воркеров про ротацию `API_TOKEN`.

## Подключить воркеры

Compose воркеры **не** поднимает. Запустите **itranscribe-worker** и **isummarize-worker** отдельно, затем зарегистрируйте их в UI хаба **Instance** (после `/setup`):

1. Поднимите каждый воркер со своим `.env` (`API_TOKEN`, у summarize ещё `BASE_URL` / `API_KEY` / `MODEL`).
2. Под instance admin: Instance → воркеры → добавить ноду:
   - `type`: `transcribe` или `summarize`
   - `base_url`: адрес, который видит **процесс хаба**, не браузер. Если хаб в Docker, а воркер на хосте: `http://host.docker.internal:8000`.
   - `api_token`: `API_TOKEN` этого воркера
   - `weight` / `enabled` по необходимости
3. Пользователи хаба эти поля не видят. Хаб копирует результат в свою БД и затем делает `DELETE` задачи на воркере.

`GET /metrics` воркеров через хаб **не** проксировать. Скрейпите каждый воркер напрямую (Bearer `API_TOKEN` воркера).

## Docker Compose

Один образ (`idigest-hub:latest`). Стадия Node собирает `web/dist`; стадия Python отдаёт API + SPA. Процесс идёт от **uid/gid 1001** (не root). Compose монтирует `./data:/data`.

### Подготовка

1. Скопируйте `.env.example` → `.env` и заполните `HUB_SECRET` / `INSTANCE_BOOTSTRAP_TOKEN` / `SESSION_SECRET` (см. [`.env`](#env)).
2. Создайте каталоги данных, если их ещё нет (SQLite, логи, загрузки). Compose монтирует `./data:/data`.

   ```bash
   mkdir -p data/uploads data/logs
   ```

   Процесс в контейнере — **uid/gid 1001**. Этот пользователь должен писать в `./data`.
   Если каталог уже есть от старого контейнера от root, один раз поправьте владельца:

   ```bash
   sudo chown -R 1001:1001 ./data
   ```

   Не делайте chmod `777`. `docker compose down` каталог `./data` не удаляет.
3. Compose ставит `COOKIE_SECURE=false` для локального HTTP. За HTTPS поставьте `COOKIE_SECURE=true` в `docker-compose.yml` (или уберите override и задайте в `.env`).

### Запуск

```bash
docker compose up --build
```

Фон: `-d`, логи: `docker compose logs -f`. Порт: `8080:8080`. Дальше откройте `http://127.0.0.1:8080/setup`.

```bash
docker compose down
```

`./data` на хосте не удаляется. После образа от root перед следующим `up` выполните `sudo chown -R 1001:1001 ./data`, если в логах `Permission denied` на `/data`.

## Типичные ошибки

| Что видно                                                            | Смысл                                                                                            |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| HTTP **401**, `error.code = bootstrap_invalid`                       | Нет/неверный `INSTANCE_BOOTSTRAP_TOKEN` на `/setup`.                                             |
| HTTP **409**, `error.code = setup_already_done`                      | Instance admin уже есть. Логиньтесь.                                                             |
| HTTP **403**, `error.code = signup_disabled`                         | Instance admin закрыл новые орги или нет неархивного signup-тарифа.                              |
| Транскрипты / токены воркеров нечитаемы после смены `HUB_SECRET`     | Ключ Fernet — `SHA-256` прежнего секрета. Верните старый `.env` или заново введите токены воркеров и смиритесь с потерей ciphertext. |
| `Permission denied` на `/data/...` (`hub.db`, `logs`, `uploads`)     | Хостовый `./data` недоступен на запись uid 1001. `sudo chown -R 1001:1001 ./data` и рестарт. Не chmod `777`. |
