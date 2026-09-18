# Skills API

Требуется auth + членство в org, если не указано иное.

## Каталог

### GET `/skills?scope=`

Опциональный фильтр: `base`, `org`, `self`, `shared`.

Возвращает `{ "items": [ skill_public + catalog, readonly, share_kind ] }`.

## Personal skills

| Method | Path | Body |
| ------ | ---- | ---- |
| POST | `/skills/self` | `{ "name", "body" }` |
| PATCH | `/skills/self/{id}` | `{ "name", "body" }` |
| DELETE | `/skills/self/{id}` | |

## Org skills (org_admin)

| Method | Path |
| ------ | ---- |
| POST | `/org/skills` |
| PATCH | `/org/skills/{id}` |
| DELETE | `/org/skills/{id}` |

## Copy

### POST `/skills/{id}/copy`

Создаёт personal copy из base, org, own или shared skill.

## Export

### GET `/skills/{id}/export`

Скачать body навыка как Markdown (`.md`). Те же правила видимости, что у чтения каталога.

## Base skills (instance_admin)

| Method | Path |
| ------ | ---- |
| GET | `/skills/base` |
| POST | `/skills/base` |
| PATCH | `/skills/base/{id}` |
| DELETE | `/skills/base/{id}` |

## Связанные страницы

- [Skills domain](../domain/skills.md)
- [Shares via Library API](library.md)
