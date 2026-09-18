# Public API (unauthenticated)

Prefix: `/api/v1`

No session or API token. Used for **read-only guest access** to summaries via public links.

Requires instance **Public URL** (`public_base_url`). Org must have `allow_public_links=true` (default). Link owner creates links from the Library UI or authenticated API — see [Library API — public links](library.md#summary-public-links).

## GET `/public/summary/{token}`

Returns summary body for an active link.

**Without PIN:** `{ "pin_required": false, "title", "body", "created_at", ... }`

**With PIN (not yet unlocked):** `{ "pin_required": true }` — no body.

**Errors:** `not_found` (404) — invalid, expired, revoked, or org policy disabled.

Rate limited per client IP and globally (Instance → Settings). Not CSRF-protected.

## POST `/public/summary/{token}/unlock`

Submit PIN when the link requires one.

```json
{ "pin": "1234" }
```

PIN: 4–6 digits. On success: `{ "pin_required": false, ... }` plus summary payload, and an HttpOnly unlock cookie (`hub_plu`, 30 min) so repeat GETs skip PIN entry.

**Errors:** `not_found` (404), `invalid_pin` (401).

Separate rate limit bucket for PIN attempts (`rate_limit_public_pin_ip`).

## Related pages

- [Library domain — public links](../domain/library.md#public-summary-links)
- [Organization API — public links policy](org.md#public-summary-links)
- [Instance API — rate limits](instance.md#settings)
