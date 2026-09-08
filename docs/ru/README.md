# idigest-hub — документация (русский)

**Язык:** [English](../en/README.md) · [Русский](README.md)

Локальный multi-tenant control plane над [itranscribe-worker](../../README.ru.md#подключить-воркеры) и [isummarize-worker](../../README.ru.md#подключить-воркеры).

**Быстрый старт:** [README проекта](../../README.ru.md)

## Архитектура

- [Обзор](architecture/overview.md) — компоненты, tenancy, поток данных
- [Поток запросов](architecture/request-flow.md) — auth, задачи, dispatcher
- [Безопасность](architecture/security.md) — секреты, шифрование, сессии, rate limit

## Доменная модель

- [Роли и доступ](domain/roles-and-access.md)
- [Организации](domain/organizations.md)
- [Биллинг и тарифы](domain/billing.md)
- [Библиотека (audio / transcripts / summaries)](domain/library.md)
- [Скилы](domain/skills.md)
- [Задачи](domain/tasks.md)

## Справочник API

- [Обзор API](api/README.md) — ошибки, auth, индекс
- [Auth](api/auth.md)
- [Tasks](api/tasks.md)
- [Library](api/library.md)
- [Organization](api/org.md)
- [Instance admin](api/instance.md)
- [Skills](api/skills.md)

## Эксплуатация

- [Деплой](operations/deployment.md)
- [Воркеры](operations/workers.md)
- [База данных](operations/database.md)
- [Troubleshooting](operations/troubleshooting.md)

## Разработка

- [Локальная настройка](development/setup.md)
- [Backend](development/backend.md)
- [Frontend](development/frontend.md)
- [Тесты](development/testing.md)
