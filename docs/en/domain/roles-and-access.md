# Roles and access

## Role matrix

| Capability | instance_admin | org_admin | org_member |
| ---------- | -------------- | --------- | ---------- |
| Instance settings, workers, tariffs | Yes | No | No |
| Impersonate users | Yes (not while impersonating) | No | No |
| Reset `org_admin` password | Yes (per org) | Yes (own org members) | No |
| View all orgs / all tasks | Yes | No | No |
| Org user management, stats | No | Yes | No |
| Org skills CRUD | No | Yes | Read-only catalog |
| Wallet / tariff (self-service) | No | Change to available tariff | No |
| Own artifacts + shared | If in org | Yes | Yes |
| Create tasks | If in org | Yes | Yes |
| Hard-delete org artifacts | No | Yes | No (own summary delete yes) |
| API tokens | Yes (no org) | If tariff.api_enabled | If tariff.api_enabled |

`instance_admin` is created once at `/setup`. They typically have **no org membership** — UI home defaults to Instance unless they join an org manually (not supported via signup flow).

## One user, one org

`memberships.user_id` is unique. A user belongs to exactly zero or one organization. Signup always creates a new personal org.

## Object visibility

For `audio`, `transcript`, `summary`:

| Viewer | Sees |
| ------ | ---- |
| Owner | Own items (hidden filter optional) |
| Org admin | All items in org |
| Org member | Own + items shared **to** them |
| Instance admin | All (when querying as admin) |

Implementation: `can_read_object()` in `app/services/access.py`.

### Hide vs delete

| Action | Who | Effect |
| ------ | --- | ------ |
| **Hide** | Owner only | `hidden_items` row — removed from default lists |
| **Delete (wipe)** | Org admin | Hard delete artifact + dependencies via `artifacts.py` |
| **Delete summary** | Owner or org admin | Hard delete single summary |

Hidden items are per-user; other org members still see the object if they have access.

## Sharing

`POST /shares` — owner shares `audio`, `transcript`, `summary`, or personal `skill` with org members (`to_user_ids`).

- Share target must be in the same org
- Recipients see `share_kind: incoming`, `shared_by` email
- Owner sees `shared_with` list
- Either party can `DELETE /shares/{share_id}`

Skills with `scope=self` can be shared; org/base skills use catalog visibility instead.

## Task visibility

| Role | Tasks visible |
| ---- | ------------- |
| instance_admin | All; optional `?org_id=` and `?user_id=` filters |
| org_admin | All tasks in org; optional `?user_id=` |
| org_member | Own tasks in org |

## Last org admin guard

Operations that would leave zero active org admins are rejected with `last_org_admin` (HTTP 409):

- Demoting/disabling the sole admin
- Offboarding without replacement

## Password lockout modes

| Condition | Allowed endpoints |
| --------- | ------------------- |
| `must_change_password` | `/me`, PATCH `/me`, password change, logout, stop impersonate |
| Password TTL expired (org setting) | Same (non–instance-admin users) |

Instance admin bypasses password TTL lock for API access patterns tied to admin workflows.

## Default landing route

Users may set `default_route` via PATCH `/me`: `library`, `skills`, `org`, `stats`, `tasks`, `instance` — only routes allowed for their role. See `web/src/routes.ts`.

## Related pages

- [Organizations](organizations.md)
- [Library](library.md)
- [Security](../architecture/security.md)
