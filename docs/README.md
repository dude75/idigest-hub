# idigest-hub documentation

**Languages:** [English](en/README.md) · [Русский](ru/README.md)

Detailed service documentation. Quick install: [README](../README.md) (EN) · [README.ru](../README.ru.md) (RU).

## Structure

```
docs/
├── en/          English
├── ru/          Русский (mirror paths)
└── assets/      Shared diagrams (language-neutral)
```

Switch language by replacing `/en/` ↔ `/ru/` in any path.

## Table of contents

### Architecture

| EN | RU |
| -- | -- |
| [Overview](en/architecture/overview.md) | [Обзор](ru/architecture/overview.md) |
| [Request flow](en/architecture/request-flow.md) | [Поток запросов](ru/architecture/request-flow.md) |
| [Security](en/architecture/security.md) | [Безопасность](ru/architecture/security.md) |

### Domain

| EN | RU |
| -- | -- |
| [Roles & access](en/domain/roles-and-access.md) | [Роли и доступ](ru/domain/roles-and-access.md) |
| [Organizations](en/domain/organizations.md) | [Организации](ru/domain/organizations.md) |
| [Billing](en/domain/billing.md) | [Биллинг](ru/domain/billing.md) |
| [Library](en/domain/library.md) | [Библиотека](ru/domain/library.md) |
| [Skills](en/domain/skills.md) | [Скилы](ru/domain/skills.md) |
| [Tasks](en/domain/tasks.md) | [Задачи](ru/domain/tasks.md) |

### API reference

| EN | RU |
| -- | -- |
| [API overview](en/api/README.md) | [Обзор API](ru/api/README.md) |
| [Auth](en/api/auth.md) | [Auth](ru/api/auth.md) |
| [Tasks](en/api/tasks.md) | [Tasks](ru/api/tasks.md) |
| [Library](en/api/library.md) | [Library](ru/api/library.md) |
| [Org](en/api/org.md) | [Org](ru/api/org.md) |
| [Instance](en/api/instance.md) | [Instance](ru/api/instance.md) |
| [Skills](en/api/skills.md) | [Skills](ru/api/skills.md) |

### Operations

| EN | RU |
| -- | -- |
| [Deployment](en/operations/deployment.md) | [Деплой](ru/operations/deployment.md) |
| [Workers](en/operations/workers.md) | [Воркеры](ru/operations/workers.md) |
| [Database](en/operations/database.md) | [База данных](ru/operations/database.md) |
| [Troubleshooting](en/operations/troubleshooting.md) | [Troubleshooting](ru/operations/troubleshooting.md) |

### Development

| EN | RU |
| -- | -- |
| [Setup](en/development/setup.md) | [Настройка](ru/development/setup.md) |
| [Backend](en/development/backend.md) | [Backend](ru/development/backend.md) |
| [Frontend](en/development/frontend.md) | [Frontend](ru/development/frontend.md) |
| [Testing](en/development/testing.md) | [Тесты](ru/development/testing.md) |

## Conventions

- **Not translated:** HTTP paths, JSON keys, error `code` values, shell commands, env var names
- **Translated:** titles, explanations, ops notes
- **Primary language for new pages:** write EN or RU first, then mirror the other tree
