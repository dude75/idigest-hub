# Биллинг и тарифы

Деньги хранятся как `Numeric(12,2)`; списания **округляются вниз до центов** (`app/money.py`).

## Поля тарифа

| Поле | Значение |
| ---- | -------- |
| `unlimited` | Если `true`, баланс не уменьшается; использование всё равно логируется с `unlimited_skip=true` |
| `available_on_signup` | Показывается при signup и разрешён для самостоятельной смены тарифа org |
| `archived_at` | Не null = архивирован; скрыт из signup, нельзя назначить новым org |
| `price_per_audio_sec` | Transcribe: длительность × ставка |
| `price_per_summarize_job` | Фиксированная плата за успешный summarize |
| `price_per_1k_summary_chars` | За 1000 символов **выходного** summary (округление вверх) |
| `signup_credit` | Начальный кошелёк при signup (игнорируется при unlimited) |
| `max_upload_bytes` | Лимит загрузки (глобально не выше 1 GiB) |
| `audio_retention_days` | `0` = хранить вечно; иначе purge job удаляет старое audio |
| `api_enabled` | Если `false`, Bearer-токены отклоняются с `api_disabled` |

Тариф по умолчанию при setup: имя `"Default"`, `unlimited=true`, `available_on_signup=true`.

## Кошелёк

- Один баланс на организацию
- **instance admin** корректирует через `POST /orgs/{org_id}/wallet` с `delta` (строковое decimal, напр. `"10.00"` или `"-5"`)
- **Ledger** — `GET /orgs/{org_id}/ledger` объединяет списания за usage и пополнения кошелька (модальное окно в Instance UI с фильтрами)
- Перед принятием новой задачи (не unlimited): `balance` должен быть **> 0**, иначе API вернёт `insufficient_balance` (HTTP 429)

Списания применяются **только при успешном завершении задачи**, один раз на задачу (защита `task.billed`).

## Снимок тарифа на задаче

При создании задачи текущие лимиты/цены тарифа копируются в строку задачи:

```
snap_unlimited
snap_price_per_audio_sec
snap_price_per_summarize_job
snap_price_per_1k_summary_chars
snap_max_upload_bytes
snap_asr_model          # только transcribe, из настроек инстанса
snap_diarization_model  # только transcribe
```

Transcribe использует настройки ASR/diarization инстанса на момент создания; summarize-снимки модели не включают.

## Формулы ценообразования

### Transcribe

```
amount = floor_to_cents(audio_duration_sec × snap_price_per_audio_sec)
```

Длительность берётся из meta результата воркера `audio_duration_sec`. Также backfill `audios.duration_sec`, если отсутствует.

### Summarize

```
job = floor_to_cents(snap_price_per_summarize_job)
units = ceil(len(summary_text) / 1000)   # 0 если пусто
text = floor_to_cents(units × snap_price_per_1k_summary_chars)
amount = job + text
```

## События использования

Каждое успешное списание создаёт строку `usage_events`:

| Поле | Содержимое |
| ---- | ---------- |
| `kind` | `transcribe` или `summarize` |
| `amount` | Сумма списания |
| `audio_sec` | Длительность transcribe |
| `summary_chars` | Длина выхода для summarize |
| `unlimited_skip` | `true`, если snap был unlimited |

Статистика org и итоги использования в `/org` агрегируют эти строки.

## Ограничение доступа к API

`org.tariff.api_enabled` должен быть `true` для:

- Bearer-аутентификации
- Создания API-токенов (список токенов показывает `blocked_by_tariff`, когда отключено)

Браузерные сессии не затрагиваются.

## Взаимодействие биллинга и хранения audio

Purge по retention (`purge_expired_audio`) удаляет audio-файлы старше `audio_retention_days`, если на них нет ссылок из задач в очереди/выполнении. Transcript/summary остаются, пока явно не удалены.

## Связанные страницы

- [Организации](organizations.md)
- [Задачи](tasks.md)
- [Instance API](../api/instance.md)
