# idigest-hub

Локальный (on-premise) **multi-tenant control plane** над [itranscribe-worker](#подключить-воркеры) и [isummarize-worker](#подключить-воркеры). Пользователи ходят только в хаб. Хаб владеет органами, ролями, кошельками, скилами, артефактами и своей очередью задач (`POST` → **202** + `task_id` → poll). Воркеры остаются внешними.

**Язык:** [English](README.md) · [Русский](README.ru.md)

**Документация:** [docs/](docs/README.md) (English · Русский)

## Что это

- Signup по умолчанию **открыт**. Из коробки — SQLite (`DATABASE_URL=sqlite:///./data/hub.db`). PostgreSQL — через ту же переменную.
- Один `instance_admin` создаётся при первом запуске (`/setup`). Остальные живут в организации (`org_admin` / `org_member`).
- Пользователи не видят URL и API-токены воркеров. Instance admin подключает воркеры в UI (базовый URL + bearer-токен).
- FastAPI отдаёт собранную SPA с того же origin (`web/dist`). Session cookie — HttpOnly + `SameSite=Lax`, без CORS.
- HTTP-порт по умолчанию **8080**, чтобы не пересечься с воркерами на `8000`.
- Compose поднимает **только хаб** и volume `./data` (PostgreSQL опционально, profile `pg`). Воркеров в этот стек не класть.

## Требования

- Python **3.12**
- Виртуальное окружение `.venv` (только `./.venv/bin/python` и `./.venv/bin/pip`)
- **Node.js** (22+) для сборки SPA в `web/`
- Диск под `./data`: файл SQLite, логи, загрузки аудио; для PostgreSQL в Compose — `./data/pg` (в git не коммитится)

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
| `DATA_DIR`                   | Корень персистентных данных (по умолчанию `./data`): логи, загрузки `{DATA_DIR}/uploads/{audio_id}/`. Файл SQLite — в этом дереве при URL по умолчанию. |
| `DATABASE_URL`               | SQLAlchemy URL (по умолчанию `sqlite:///./data/hub.db`). Для PostgreSQL: `postgresql+psycopg://user:pass@host:5432/db`. **Смена URL — другая БД с другими данными**, автоматической миграции SQLite ↔ PostgreSQL нет. |
| `SQLITE_PATH`                | Legacy fallback, если `DATABASE_URL` пуст (по умолчанию `./data/hub.db`). Лучше задавать `DATABASE_URL`. |
| `LOG_DIR`                    | Каталог прикладных логов (по умолчанию `./data/logs`).                                                                                                           |
| `LOG_ENABLED`                | Прикладной лог-файл + app-logger. По умолчанию `true`. `false` / `0` / `no` — выкл.                                                                              |
| `LOG_MAX_BYTES`              | Ротация `app.log` при превышении размера в байтах. По умолчанию `5242880` (5 MiB).                                                                               |
| `LOG_BACKUP_COUNT`           | Сколько архивов хранить (`app.log.1` … `app.log.N`). По умолчанию `5`.                                                                                           |
| `COOKIE_SECURE`              | Флаг `Secure` у session cookie. По умолчанию `false` (локальный HTTP). За HTTPS ставьте `true`.                                                                  |

Всё, что должно пережить рестарт, лежит в `./data` (SQLite `hub.db` или `./data/pg` для PostgreSQL в Compose, логи **и загрузки** `{DATA_DIR}/uploads/{audio_id}/`). В Docker монтируйте этот каталог. Контейнер Compose пишет в него от uid/gid **1001** (см. [Docker Compose](#docker-compose)).

`api_token` воркеров, JSON транскриптов, тела саммари и SMTP-пароль в БД хаба хранятся в Fernet (AES-128-CBC + HMAC). Ключ — `SHA-256(HUB_SECRET)`, не сырой секрет — та же идея, что `API_TOKEN` у воркеров. API по-прежнему отдаёт открытый текст авторизованным клиентам. Аудио на диске в этой версии **не** шифруется. Это защита только от утечки БД без `.env`.

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

По умолчанию хаб на SQLite (`DATABASE_URL=sqlite:////data/hub.db` в контейнере). PostgreSQL — отдельный сервис под profile **`pg`**, данные в `./data/pg` на хосте.

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

### Запуск (SQLite, по умолчанию)

```bash
docker compose up --build
```

Фон: `-d`, логи: `docker compose logs -f`. Порт: `8080:8080`. Дальше откройте `http://127.0.0.1:8080/setup`.

### Запуск (PostgreSQL)

В `.env`:

```env
DATABASE_URL=postgresql+psycopg://hub:hub@postgres:5432/hub
POSTGRES_USER=hub
POSTGRES_PASSWORD=hub
POSTGRES_DB=hub
```

Затем:

```bash
docker compose --profile pg up --build
```

PostgreSQL хранит файлы в `./data/pg` (bind mount). Загрузки и логи — по-прежнему `./data/uploads` и `./data/logs`. Это **отдельная** БД от SQLite: при возврате к обычному `docker compose up` пользователи и задачи не переносятся.

Если PostgreSQL не стартует из‑за прав, один раз на хосте:

```bash
sudo chown -R 999:999 ./data/pg
```

### Остановка

```bash
docker compose down
```

`./data` на хосте не удаляется. После образа от root перед следующим `up` выполните `sudo chown -R 1001:1001 ./data`, если в логах `Permission denied` на `/data`.

## Ограничение частоты запросов

Хаб опционально ограничивает частоту запросов **в памяти процесса** (один worker Uvicorn — см. [Установка и запуск](#установка-и-запуск)). После рестарта счётчики обнуляются. Фоновая очистка удаляет протухшие bucket'ы; в RAM хранится не более **20 000** bucket'ов (при переполнении удаляются самые старые).

**Настройка:** instance admin → **Instance** → **Settings**. Общий переключатель: **Enable rate limiting**. **`0`** отключает конкретное правило.

### Что ограничивается

| Трафик | Ключи | Примечание |
| ------ | ----- | ---------- |
| Auth (`/auth/login`, signup, reset, `/setup`) | **email**, **IP клиента**, **global** | До тяжёлой работы (bcrypt на login). |
| Программный API | только **`Authorization: Bearer`** | **user id**, **IP**, **global**; отдельно `POST /tasks/transcribe` и `POST /tasks/summarize`. Cookie-сессия **не** попадает под API-limit. |

При превышении: HTTP **429**, `error.code = rate_limited`, заголовок `Retry-After` (секунды).

### Значения по умолчанию

| Правило | На email / user | На IP | Global | Окно |
| ------- | --------------- | ----- | ------ | ---- |
| Login | 30 / мин | **0 (выкл.)** | 500 / мин | 1 мин |
| Signup | 10 / мин | **0** | 100 / мин | 1 мин |
| Reset пароля | 10 / час | **0** | 50 / час | 1 час |
| Reset confirm | — | **0** | 100 / час | 1 час |
| Setup | — | **0** | 10 / час | 1 час |
| Bearer API | 120 / мин | **0** | 2000 / мин | 1 мин |
| Создание task | 30 / мин | **0** | — | 1 мин |

### IP клиента за reverse proxy

По умолчанию hub видит **адрес TCP-соединения** (`request.client.host`) — обычно reverse proxy, не браузер.

- Если прокси **не** передаёт реальный IP, у всех может быть один IP в лимитах hub. Лимиты по email/user работают; per-IP выключен (`0`), пока не зададите значение в Settings.
- Для **реальных IP** прокси может слать `X-Forwarded-For` или `X-Real-IP`; поддержка trusted proxy может быть добавлена позже. **Не** доверять заголовкам, если hub доступен из интернета напрямую.

Пример (nginx перед hub):

```nginx
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Real-IP $remote_addr;
```

Грубое ограничение по IP на **reverse proxy** тоже допустимо; для работы hub настройки прокси **не обязательны**.

### Эксплуатация

- Всегда **`--workers 1`**: лимиты на процесс.
- `/api/v1/health` и статика не лимитируются.

## Типичные ошибки

| Что видно                                                            | Смысл                                                                                            |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| HTTP **401**, `error.code = bootstrap_invalid`                       | Нет/неверный `INSTANCE_BOOTSTRAP_TOKEN` на `/setup`.                                             |
| HTTP **409**, `error.code = setup_already_done`                      | Instance admin уже есть. Логиньтесь.                                                             |
| HTTP **403**, `error.code = signup_disabled`                         | Instance admin закрыл новые орги или нет неархивного signup-тарифа.                              |
| Транскрипты / токены воркеров нечитаемы после смены `HUB_SECRET`     | Ключ Fernet — `SHA-256` прежнего секрета. Верните старый `.env` или заново введите токены воркеров и смиритесь с потерей ciphertext. |
| `Permission denied` на `/data/...` (`hub.db`, `logs`, `uploads`)     | Хостовый `./data` недоступен на запись uid 1001. `sudo chown -R 1001:1001 ./data` и рестарт. Не chmod `777`. |
| HTTP **429**, `error.code = rate_limited`                              | Слишком много запросов; подождите `Retry-After` или поднимите лимиты в Instance → Settings.                  |
