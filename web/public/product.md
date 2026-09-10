# idigest-hub

**idigest-hub** is a self-hosted, multi-tenant control plane for audio transcription and AI summarization. Organizations upload recordings, receive transcripts, and run configurable skills to produce meeting notes, reports, and digests. Transcription and summarization workers run on your infrastructure; users interact only with the hub. Data stays inside your perimeter.

## What it does

Upload audio (MP3, WAV, M4A, and more) via the web UI or REST API. The hub enqueues a job; an external worker transcribes speech. Run a skill to extract key points, decisions, and action items. Audio, transcripts, and summaries live in a shared library with search, sharing, and export.

## Deployment

- **On-premise / self-hosted** — Docker, SQLite or PostgreSQL, default HTTP port 8080
- **Workers** — connect itranscribe-worker and isummarize-worker on your network; users never see worker URLs or tokens
- **Data** — audio, transcripts, and summaries stored on your disk (`./data` volume or attached storage)
- **Monitoring** — Prometheus metrics at `/metrics`, Grafana dashboard included

## Key features

| Feature | Description |
| --- | --- |
| Transcription | Queue-based speech-to-text via external workers |
| AI summaries | Configurable skills for meeting notes, reports, long-recording digests |
| Library | Audio, transcripts, and summaries in one searchable place |
| Organizations | Multi-tenant: separate plans, wallets, members per org |
| Roles | `org_admin` and `org_member` with role-based access |
| Billing | Plans, upload limits, audio retention, pay-as-you-go metering |
| SSO | OIDC-compatible login (Keycloak and other IdPs) at the org level |
| API | REST API for transcription and summarization jobs (plan-gated tokens) |

## Who it's for

- **IT teams** — deploy on-prem with Docker, PostgreSQL, Prometheus; full data control
- **Managers** — automatic meeting notes with decisions and tasks
- **Researchers** — interviews, lectures, focus groups to text in minutes
- **Content teams** — podcasts and webinars into draft posts and scripts

## Enterprise FAQ

**Is it built for on-premise?** Yes. Self-hosted control plane inside your perimeter (Docker, your PostgreSQL), no SaaS data egress.

**Data sovereignty?** Artifacts live on your storage. Retention follows each org's plan. Workers and tokens are hidden from end users.

**Corporate SSO?** Per-org OIDC (Keycloak and other OpenID Connect IdPs). Org admins enable SSO; employees use the corporate provider.

**Team isolation?** Each organization is a separate tenant with its own plan, wallet, members, and roles. Artifact sharing stays within the org.

**Audit and API?** Wallets with operation ledgers, audit logging, metered usage, REST job submission.

**Production?** Prometheus `/metrics`, Grafana dashboard, rate limits, health checks, HTTPS. Use PostgreSQL and dedicated workers for resilience.

## Pricing

Plans and pricing are shown on the landing page (`/#pricing`) after signup tariffs are configured on the instance.

## Links

- Landing page: `/`
- Source: https://github.com/dude75/idigest-hub
