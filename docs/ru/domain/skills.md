# Навыки (Skills)

**Skills** — шаблоны промптов (имя + markdown/text body), используемые при summarize transcript. Хаб конкатенирует выбранные навыки и отправляет их summarize-воркеру как параметр `skill`.

## Области видимости (scopes)

| scope | Владелец | Кто редактирует | Видимость |
| ----- | -------- | --------------- | --------- |
| `base` | instance (глобальный) | instance_admin через `/skills/base` | Все org, только чтение в UI |
| `org` | organization | org_admin через `/org/skills` | Все участники org |
| `self` | user | владелец через `/skills/self` | Владелец + получатели share |

Catalog endpoint `GET /skills?scope=` возвращает объединённое представление с метаданными:

- `catalog`: `base` | `org` | `self` | `shared`
- `readonly`: `true` для base, shared, org (не admin), org-навыков для members

## Доступность для summarize

При создании `POST /tasks/summarize` каждый `skill_id` должен быть доступен:

| scope | Правило |
| ----- | ------- |
| `base` | Всегда разрешён |
| `org` | Та же org |
| `self` | Владелец или расшарено пользователю |

Навыки объединяются в порядке запроса:

```markdown
## Skill Name One

Body text...

## Skill Name Two

Body text...
```

## CRUD персональных навыков

| Method | Path |
| ------ | ---- |
| POST | `/skills/self` |
| PATCH | `/skills/self/{id}` |
| DELETE | `/skills/self/{id}` |

## CRUD org-навыков (org_admin)

| Method | Path |
| ------ | ---- |
| POST | `/org/skills` |
| PATCH | `/org/skills/{id}` |
| DELETE | `/org/skills/{id}` |

## CRUD base-навыков (instance_admin)

| Method | Path |
| ------ | ---- |
| GET | `/skills/base` |
| POST | `/skills/base` |
| PATCH | `/skills/base/{id}` |
| DELETE | `/skills/base/{id}` |

## Копирование

`POST /skills/{id}/copy` — создаёт `self`-навык для текущего пользователя с тем же name/body. Разрешено из base, org-навыка той же org, собственного self-навыка или расшаренного self-навыка.

## Шаринг self-навыков

`POST /shares` с `object_type: "skill"` — только для `scope=self`, принадлежащих отправителю. Получатели видят навык под `catalog: shared` (readonly). Могут скопировать в свою библиотеку.

## Связанные страницы

- [Задачи](tasks.md)
- [Библиотека](library.md)
- [Skills API](../api/skills.md)
