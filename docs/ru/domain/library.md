# Библиотека: audio, transcripts, summaries

**Библиотека (library)** — org-scoped хранилище пользовательских артефактов. Конвейер: **Audio → Transcript → Summary**.

## Audio

### Загрузка

`POST /audios` — multipart `file`

| Правило | Значение |
| ------- | -------- |
| Разрешённые расширения | `.wav`, `.mp3`, `.m4a` |
| Макс. размер | `min(tariff.max_upload_bytes, 1 GiB)` |
| Хранение | `STORAGE_BACKEND=local`: `{DATA_DIR}/uploads/{audio_id}/original{suffix}`. `STORAGE_BACKEND=s3`: `s3://{bucket}/uploads/{audio_id}/original{suffix}` (SSE при upload). |

Неверное расширение → `invalid_file`. Превышение лимита → `payload_too_large`.

### Endpoints

| Method | Path | Доступ |
| ------ | ---- | ------ |
| GET | `/audios` | Список видимых (см. роли) |
| GET | `/audios/{id}` | Детали + id transcript |
| GET | `/audios/{id}/file` | Поток или скачивание оригинала (`?download=true`) |
| POST | `/audios/{id}/hide` | Владелец |
| POST | `/audios/{id}/unhide` | Владелец |
| DELETE | `/audios/{id}` | org_admin wipe |

Query `include_hidden=true` в списке включает скрытые объекты владельца.

### Доступность transcribe

`can_transcribe` в деталях audio равен `true`, когда файл ещё существует на диске.

## Transcripts

Создаются успешными **transcribe tasks**, не загружаются напрямую.

- Utterances хранятся зашифрованными в БД как JSON-массив: `[{ "speaker": "...", "text": "..." }, ...]`
- `source_audio_id` ссылается на источник (nullable после hard-delete audio через SET NULL)
- GET detail возвращает расшифрованные `utterances` + связанные summaries

Опциональное поле `title`; редактирование через `PATCH /transcripts/{id}`. Export: `GET /transcripts/{id}/export?format=txt|json`.

Hide/unhide/delete по тому же шаблону, что у audio (delete = org_admin wipe).

## Summaries

Создаются успешными **summarize tasks**.

| Поле | Примечания |
| ---- | ---------- |
| `skill_ids` | JSON-список UUID навыков |
| `edited` | `true`, если пользователь PATCHил body |
| `source_transcript_id` | Происхождение |

### Редактирование

`PATCH /summaries/{id}` — владелец или org_admin может обновить `body` и/или `title`. Изменение body устанавливает `edited=true`, перешифровывает body, запись в audit log.

### Hide / export

Тот же hide/unhide, что у audio и transcripts. Список поддерживает `include_hidden=true`. Export: `GET /summaries/{id}/export?format=md|txt` (убирает markdown code fences из вывода воркера).

### Удаление

Владелец или org_admin — hard delete (не то же самое, что org wipe endpoints для audio/transcript).

## Шаринг

Поделиться audio, transcript, summary или персональным skill с коллегами в org:

```json
POST /shares
{
  "object_type": "transcript",
  "object_id": "...",
  "to_user_ids": ["...", "..."]
}
```

Получатели получают read-доступ (и могут использовать расшаренный transcript в summarize, если есть доступ к навыкам). Ответ: `{ "ids": ["share_id", ...] }`.

Список получателей: `GET /shares?object_type=...&object_id=...` (владелец). UI показывает получателей и позволяет отозвать доступ.

Отзыв: `DELETE /shares/{share_id}` — владелец или получатель.

## Резервная копия профиля

`GET /me/backup` — ZIP или TGZ своих transcripts, summaries и/или personal skills (страница Profile в UI).

## Алгоритм видимости списка

Для org member (не admin):

1. Включить, если владелец
2. Включить, если расшарено пользователю
3. Если владелец и скрыто (и нет `include_hidden`), исключить

org admin видит все строки org независимо от share/hide.

## Каскад hard delete

`hard_delete_audio` / `hard_delete_transcript` / `hard_delete_summary` в `app/services/artifacts.py`:

- Удаляет файлы, строки БД, shares, hidden_items
- Выполняющиеся задачи, ссылающиеся на артефакт, могут получить `skip_persist` / `source_deleted`

DELETE org admin на audio/transcript разрушителен для всего org-представления.

## Связанные страницы

- [Задачи](tasks.md)
- [Навыки](skills.md)
- [Library API](../api/library.md)
