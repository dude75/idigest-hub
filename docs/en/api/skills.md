# Skills API

Auth + org membership required unless noted.

## Catalog

### GET `/skills?scope=`

Optional filter: `base`, `org`, `self`, `shared`.

Returns `{ "items": [ skill_public + catalog, readonly, share_kind ] }`.

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

Creates personal copy from base, org, own, or shared skill.

## Export

### GET `/skills/{id}/export`

Download skill body as Markdown (`.md`). Same visibility as catalog read access.

## Base skills (instance_admin)

| Method | Path |
| ------ | ---- |
| GET | `/skills/base` |
| POST | `/skills/base` |
| PATCH | `/skills/base/{id}` |
| DELETE | `/skills/base/{id}` |

MCP equivalents: [MCP tools](mcp.md) — `list_skills`, `get_skill`, `create_skill` (`catalog`: `self` / `org` / `base`), `update_skill`, `delete_skill`. Scopes: `skills:read` / `skills:write`.

## Related pages

- [Skills domain](../domain/skills.md)
- [Shares via Library API](library.md)
- [MCP tools](mcp.md)
