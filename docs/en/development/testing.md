# Testing

Framework: **pytest** with FastAPI `TestClient`.

Config: `pytest.ini`, fixtures in `tests/conftest.py`.

## Running

```bash
./.venv/bin/pytest              # all tests
./.venv/bin/pytest tests/test_auth.py -v
```

## Test isolation

Each test gets:

- Fresh SQLite file in `tmp_path`
- Env vars: test secrets, `LOG_ENABLED=false`, short `DISPATCH_NO_CANDIDATE_SEC`
- `DISPATCH_POLL_SEC=3600` to silence background dispatcher noise
- Reset engine, rate limiter, dispatcher lock

## Helpers (conftest)

| Helper | Purpose |
| ------ | ------- |
| `setup_admin(client)` | POST `/setup` |
| `signup(client, email, password, tariff_id)` | New org user |
| `login(client, email, password)` | Session cookie |
| `err_code(response)` | Parse `error.code` |
| Worker mocks | Patch httpx2 worker calls |

## Test modules

| File | Coverage |
| ---- | -------- |
| `test_auth.py` | Setup, signup, login, tokens, password |
| `test_tasks.py` | Transcribe/summarize, dispatch, billing |
| `test_library.py` | Upload, shares, hide |
| `test_org.py` | Users, offboarding, stats |
| `test_instance.py` | Workers, tariffs, settings |
| `test_billing.py` | Wallet, charges, unlimited |
| `test_rate_limit.py` | Limiter buckets |

## Mocking workers

Tests patch `app.services.workers` or dispatcher health to simulate `loaded` engines without real workers.

Pattern: return synthetic success JSON from `post_transcribe` / `get_task`.

## Writing new tests

1. Use `client` fixture
2. Bootstrap admin or signup user
3. Assert status code + `err_code()` on failures
4. Prefer deterministic dispatch (`locked_tick` runs in request path)

## CI considerations

- No Node required for backend tests
- Build web separately if testing full stack manually

## Related pages

- [Development setup](setup.md)
- [Backend layout](backend.md)
