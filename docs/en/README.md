# idigest-hub — documentation (English)

**Language:** [English](README.md) · [Русский](../ru/README.md)

On-premise multi-tenant control plane for [itranscribe-worker](https://github.com/dude75/itranscribe-worker) and [isummarize-worker](https://github.com/dude75/isummarize-worker).

**Quick start:** [Project README](../../README.md)

## Compliance (auditors)

- [Enterprise security brief](compliance/auditor-brief.md) — control domains, evidence index, ISO/SOC mapping, shared responsibility
- [SECURITY.md](../../SECURITY.md) — CI/CD policy and vulnerability management

## Architecture

- [Overview](architecture/overview.md) — components, tenancy, data flow
- [Request flow](architecture/request-flow.md) — auth, tasks, dispatcher sequences
- [Security](architecture/security.md) — envelope encryption, KEK/DEK rotation, sessions, rate limits

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
- [Public summary links (guest)](api/public.md)

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
