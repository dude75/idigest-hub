# Organizations

An **organization** is the billing and data isolation boundary. Every regular user belongs to exactly one org via `memberships`.

## Creation paths

### Signup (`POST /auth/signup`)

1. Instance must be bootstrapped (`bootstrap_done`)
2. `allow_new_orgs` must be true
3. At least one non-archived tariff with `available_on_signup=true`
4. Creates user + personal org (`is_personal=true`, name from email local-part)
5. User becomes `org_admin`
6. Initial balance = `signup_credit` (or `0` if tariff is `unlimited`)

### Org admin invites (`POST /org/users`)

Org admin creates users with email, password, role (`org_admin` | `org_member`), locale. New user is added to **the same org**.

## Org profile

| Field | Editable by | Notes |
| ----- | ----------- | ----- |
| `name` | org_admin | Display name |
| `tariff_id` | org_admin (self) or instance_admin | Must be non-archived and `available_on_signup` for self-service |
| `password_ttl_days` | org_admin | `0` = disabled; forces periodic password change |
| `balance` | instance_admin (wallet) | Decimal(12,2), floored to cents on charge |

GET `/org` returns org + embedded tariff + usage total (`sum(usage_events.amount)`).

## Tariff change

**Org admin** — `PATCH /org/tariff`: only tariffs that are active and flagged `available_on_signup`.

**Instance admin** — `PATCH /instance/orgs/{org_id}/tariff`: can assign any non-archived tariff.

Changing tariff does **not** alter snapshotted prices on existing tasks.

## User lifecycle

| Action | Endpoint | Notes |
| ------ | -------- | ----- |
| Change role | `PATCH /org/users/{id}` | Cannot demote last org admin |
| Disable | `POST /org/users/{id}/disable` | Invalidates sessions + API tokens |
| Enable | `POST /org/users/{id}/enable` | |
| Admin reset password | `POST /org/users/{id}/reset-password` | Sets random password, `must_change_password=true` |
| Offboard | `POST /org/users/{id}/offboard` | See below |

## Offboarding

`POST /org/users/{id}/offboard` body:

| action | Behavior |
| ------ | -------- |
| `transfer` | Reassign artifacts to `target_user_id` (same org) |
| `wipe` | Hard-delete user's content |

Guard: cannot offboard last org admin without replacement.

## Statistics

`GET /org/stats?from=YYYY-MM-DD&to=YYYY-MM-DD` — org_admin only.

Aggregates `usage_events` by day, user, kind (`transcribe` | `summarize`). Optional filters: `user_id`, `kind`.

Instance-level stats: `GET /instance/stats` (completed jobs, instance admin).

## Signup disable

Instance admin sets `allow_new_orgs=false` or archives all signup tariffs → new signups return `signup_disabled` (HTTP 403).

Existing orgs continue to operate.

## Personal vs team orgs

`is_personal=true` for signup-created orgs. No behavioral difference in API — flag is informational for UI.

## Related pages

- [Billing](billing.md)
- [Roles and access](roles-and-access.md)
- [Org API](../api/org.md)
