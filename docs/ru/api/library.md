# Library API

Требуется auth. Членство в org обязательно для всех эндпоинтов.

## Audio

| Method | Path | Описание |
| ------ | ---- | -------- |
| POST | `/audios` | Multipart upload (поле `file`; опционально `from_microphone=true` → extract в MP3). В ответе `user_tags` с автотегом [источника ingest](../domain/library.md#теги-источника-ingest-автоматически). |
| GET | `/audios?include_hidden=false&tag=` | Список (`tag` — id или имя вашего тега) |
| GET | `/audios/{id}` | Детали + список transcript + `can_transcribe` |
| GET | `/audios/{id}/file` | Потоковая отдача или скачивание (`?download=true`) |
| POST | `/audios/{id}/hide` | Скрытие владельцем |
| POST | `/audios/{id}/unhide` | Показ владельцем |
| DELETE | `/audios/{id}` | Жёсткое удаление org_admin |

Элементы списка/деталей включают share badges: `share_kind`, `shared_with`, `shared_by`, `hidden`, `owner_email`, и **`user_tags`** (личные теги текущего пользователя: `{ "id", "name" }[]`, другим не видны).

### GET `/capture/platforms`

Discovery capture встреч: `{ "enabled", "connectors": [{ "id", "label" }], "jitsi_hosts": [] }`. См. [Tasks API](tasks.md#get-captureplatforms).

## Transcripts

| Method | Path | Описание |
| ------ | ---- | -------- |
| GET | `/transcripts?include_hidden=false&tag=` | Список |
| GET | `/transcripts/{id}` | Детали с массивом `utterances` |
| PATCH | `/transcripts/{id}` | `{ "title": "..." }` — владелец или org_admin |
| GET | `/transcripts/{id}/export?format=txt\|json` | Скачать transcript |
| POST | `/transcripts/{id}/hide` | Владелец |
| POST | `/transcripts/{id}/unhide` | Владелец |
| DELETE | `/transcripts/{id}` | Удаление org_admin |

Форма utterance:

```json
{
  "speaker": "SPEAKER_00",
  "text": "Hello world"
}
```

## Summaries

| Method | Path | Описание |
| ------ | ---- | -------- |
| GET | `/summaries?include_hidden=false&tag=` | Список |
| GET | `/summaries/{id}` | Детали с `body` |
| GET | `/summaries/{id}/export?format=md\|txt` | Скачать summary (markdown fences убираются) |
| PATCH | `/summaries/{id}` | `{ "body": "..." }` и/или `{ "title": "..." }` — владелец или org_admin |
| POST | `/summaries/{id}/hide` | Владелец |
| POST | `/summaries/{id}/unhide` | Владелец |
| DELETE | `/summaries/{id}` | Владелец или org_admin |

### Публичные ссылки на summary

Read-only гостевой URL (нужны Public URL + org `allow_public_links`).

| Method | Path | Доступ |
| ------ | ---- | ------ |
| GET | `/summaries/{id}/public-link` | Владелец или org_admin |
| POST | `/summaries/{id}/public-link` | Только владелец |
| DELETE | `/summaries/{id}/public-link` | Владелец или org_admin |

**Тело POST:**

```json
{
  "expires_in_days": 7,
  "pin": "1234"
}
```

- `expires_in_days`: опционально; omit или `null` — без срока; `<= 0` — ошибка
- `pin`: опционально 4–6 цифр; omit — без PIN

Ответ `{ "link": { "id", "summary_id", "url", "expires_at", "pin_required", "created_at", "revoked" } }`. Повторное создание заменяет предыдущую ссылку (новый token).

Ошибки: `public_base_url_missing` (400), `public_links_disabled` (403).

Гостевой доступ (без auth): [public.md](public.md).

## Личные теги (без ACL)

Метки пользователя на объектах библиотеки, к которым у него есть доступ (свои, shared, org_admin). Чужие пользователи ваши теги не видят.

| Method | Path | Описание |
| ------ | ---- | -------- |
| GET | `/tags` | Каталог: `{ "items": [{ "id", "name", "usage_count" }, ...] }` |
| PATCH | `/tags/{tag_id}` | `{ "name": "..." }` — переименование |
| DELETE | `/tags/{tag_id}` | Удалить тег со всех ваших объектов |
| PUT | `/object-tags` | `{ "object_type": "audio\|transcript\|summary", "object_id": "uuid", "tags": ["имя", ...] }` — заменить теги на объекте (создаёт по имени) |

**Теги источника ingest:** при создании audio (upload, import, capture) hub добавляет владельцу один тег (`upload`, `mic`, платформа или connector — см. [domain](../domain/library.md#теги-источника-ingest-автоматически)). Import/capture ставят тег при успешном завершении ingest-задачи.

Списки поддерживают `tag` (id или имя без учёта регистра) для фильтрации.

MCP: [инструменты MCP](mcp.md#личные-теги) — `list_tags`, `rename_tag`, `delete_tag`, `set_object_tags`; в list-инструментах опциональный `tag`.

## Shares

### GET `/shares?object_type=...&object_id=...`

Только владелец. Исходящие shares: `{ "items": [{ "id", "to_user_id", "to_email", "created_at" }, ...] }`.

### POST `/shares`

```json
{
  "object_type": "audio|transcript|summary|skill",
  "object_id": "uuid",
  "to_user_ids": ["uuid", "uuid"]
}
```

Возвращает `{ "ids": ["share_id", ...] }`. Пропускает self и неизвестных членов org.

### DELETE `/shares/{share_id}`

Отозвать может владелец или получатель.

Эквиваленты MCP (OAuth JWT, те же правила доступа): [MCP tools](mcp.md) — `list_audios` / `get_audio` / `create_audio_upload` / `delete_audio`, `list_transcripts` / `get_transcript` / `update_transcript` / `delete_transcript`, `list_summaries` / `get_summary` / `update_summary` / `delete_summary`.

## Связанные страницы

- [Library domain](../domain/library.md)
- [Tasks API](tasks.md)
- [MCP tools](mcp.md)
