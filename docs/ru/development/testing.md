# Тестирование

Framework: **pytest** с FastAPI `TestClient`.

Конфигурация: `pytest.ini`, fixtures в `tests/conftest.py`.

## Запуск

```bash
./.venv/bin/pytest              # all tests
./.venv/bin/pytest tests/test_auth.py -v
```

## Изоляция тестов

Каждый тест получает:

- Новый SQLite file в `tmp_path`
- Env vars: test secrets, `LOG_ENABLED=false`, short `DISPATCH_NO_CANDIDATE_SEC`
- `DISPATCH_POLL_SEC=3600` чтобы заглушить фоновый шум dispatcher
- Сброс engine, rate limiter, dispatcher lock

## Helpers (conftest)

| Helper | Назначение |
| ------ | ---------- |
| `setup_admin(client)` | POST `/setup` |
| `signup(client, email, password, tariff_id)` | New org user |
| `login(client, email, password)` | Session cookie |
| `err_code(response)` | Parse `error.code` |
| Worker mocks | Patch httpx2 worker calls |

## Test modules

| File | Покрытие |
| ---- | -------- |
| `test_auth.py` | Setup, signup, login, tokens, password |
| `test_tasks.py` | Transcribe/summarize, dispatch, billing |
| `test_library.py` | Upload, shares, hide |
| `test_org.py` | Users, offboarding, stats |
| `test_instance.py` | Workers, tariffs, settings |
| `test_billing.py` | Wallet, charges, unlimited |
| `test_rate_limit.py` | Limiter buckets |

## Mocking workers

Tests патчат `app.services.workers` или dispatcher health, чтобы симулировать `loaded` engines без реальных workers.

Паттерн: return synthetic success JSON from `post_transcribe` / `get_task`.

## Написание новых тестов

1. Используйте fixture `client`
2. Bootstrap admin или signup user
3. Assert status code + `err_code()` при failures
4. Предпочитайте deterministic dispatch (`locked_tick` выполняется в request path)

## Заметки для CI

- Node не требуется для backend tests
- Build web отдельно, если тестируете full stack вручную

## Связанные страницы

- [Development setup](setup.md)
- [Backend layout](backend.md)
