# Library API

Требуется auth. Членство в org обязательно для всех эндпоинтов.

## Audio

| Method | Path | Описание |
| ------ | ---- | -------- |
| POST | `/audios` | Multipart upload (поле `file`) |
| GET | `/audios?include_hidden=false` | Список |
| GET | `/audios/{id}` | Детали + список transcript + `can_transcribe` |
| GET | `/audios/{id}/file` | Потоковая загрузка файла |
| POST | `/audios/{id}/hide` | Скрытие владельцем |
| POST | `/audios/{id}/unhide` | Показ владельцем |
| DELETE | `/audios/{id}` | Жёсткое удаление org_admin |

Элементы списка/деталей включают share badges: `share_kind`, `shared_with`, `shared_by`, `hidden`, `owner_email`.

## Transcripts

| Method | Path | Описание |
| ------ | ---- | -------- |
| GET | `/transcripts?include_hidden=false` | Список |
| GET | `/transcripts/{id}` | Детали с массивом `utterances` |
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
| GET | `/summaries` | Список |
| GET | `/summaries/{id}` | Детали с `body` |
| PATCH | `/summaries/{id}` | `{ "body": "..." }` — владелец или org_admin |
| DELETE | `/summaries/{id}` | Владелец или org_admin |

## Shares

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

## Связанные страницы

- [Library domain](../domain/library.md)
- [Tasks API](tasks.md)
