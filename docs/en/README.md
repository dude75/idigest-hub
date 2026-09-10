# idigest-hub — documentation (English)

**Language:** [English](README.md) · [Русский](../ru/README.md)

On-premise multi-tenant control plane for [itranscribe-worker](../../README.md#attach-workers) and [isummarize-worker](../../README.md#attach-workers).

**Quick start:** [Project README](../../README.md)

## Architecture

- [Overview](architecture/overview.md) — components, tenancy, data flow
- [Request flow](architecture/request-flow.md) — auth, tasks, dispatcher sequences
- [Security](architecture/security.md) — secrets, encryption, sessions, rate limits

## Domain model

- [Roles and access](domain/roles-and-access.md)
- [Organizations](domain/organizations.md)
- [Billing and tariffs](domain/billing.md)
- [Library (audio / transcripts / summaries)](domain/library.md)
- [Skills](domain/skills.md)
- [Tasks](domain/tasks.md)

## API reference

- [API overview](api/README.md) — errors, auth, index
- [Auth](api/auth.md)
- [Tasks](api/tasks.md)
- [Library](api/library.md)
- [Organization](api/org.md)
- [Instance admin](api/instance.md)
- [Skills](api/skills.md)

## Operations

- [Deployment](operations/deployment.md)
- [Monitoring](operations/monitoring.md)
- [Workers](operations/workers.md)
- [Database](operations/database.md)
- [Troubleshooting](operations/troubleshooting.md)

## Development

- [Local setup](development/setup.md)
- [Backend layout](development/backend.md)
- [Frontend layout](development/frontend.md)
- [Testing](development/testing.md)
