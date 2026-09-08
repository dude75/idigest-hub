# Библиотека: audio, transcripts, summaries

**Библиотека (library)** — org-scoped хранилище пользовательских артефактов. Конвейер: **Audio → Transcript → Summary**.

## Audio

### Загрузка

`POST /audios` — multipart `file`

| Правило | Значение |
| ------- | -------- |
| Разрешённые расширения | `.wav`, `.mp3`, `.m4a` |
| Макс. размер | `min(tariff.max_upload_bytes, 1 GiB)` |
| Путь хранения | `{DATA_DIR}/uploads/{audio_id}/original{suffix}` |

Неверное расширение → `invalid_file`. Превышение лимита → `payload_too_large`.

### Endpoints

| Method | Path | Доступ |
| ------ | ---- | ------ |
| GET | `/audios` | Список видимых (см. роли) |
| GET | `/audios/{id}` | Детали + id transcript |
| GET | `/audios/{id}/file` | Скачать оригинал |
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

Hide/unhide/delete по тому же шаблону, что у audio (delete = org_admin wipe).

## Summaries

Создаются успешными **summarize tasks**.

| Поле | Примечания |
| ---- | ---------- |
| `skill_ids` | JSON-список UUID навыков |
| `edited` | `true`, если пользователь PATCHил body |
| `source_transcript_id` | Происхождение |

### Редактирование

`PATCH /summaries/{id}` — владелец или org_admin может обновить `body`. Устанавливает `edited=true`, перешифровывает body, запись в audit log.

### Удаление

Владелец или org_admin — hard delete (не то же самое, что org wipe endpoints для audio/transcript).

Список summaries всегда включает скрытые элементы для фильтрации владельцем (переключателя hide в list API для summaries нет — бейджи hide всё равно применяются, если заданы).

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

Отзыв: `DELETE /shares/{share_id}` — владелец или получатель.

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
