# Skills

**Skills** are prompt templates (name + markdown/text body) used when summarizing transcripts. The hub concatenates selected skills and sends them to the summarize worker as the `skill` parameter.

## Scopes

| scope | Owner | Who can edit | Visibility |
| ----- | ----- | ------------ | ------------ |
| `base` | instance (global) | instance_admin via `/skills/base` | All orgs, read-only in UI |
| `org` | organization | org_admin via `/org/skills` | All members of org |
| `self` | user | owning user via `/skills/self` | Owner + share recipients |

Catalog endpoint `GET /skills?scope=` returns merged view with metadata:

- `catalog`: `base` | `org` | `self` | `shared`
- `readonly`: true for base, shared, org (non-admin), org skills for members

## Summarize eligibility

When creating `POST /tasks/summarize`, each `skill_id` must be accessible:

| scope | Rule |
| ----- | ---- |
| `base` | Always allowed |
| `org` | Same org |
| `self` | Owner or shared with user |

Skills are combined in request order:

```markdown
## Skill Name One

Body text...

## Skill Name Two

Body text...
```

## Personal skills CRUD

| Method | Path |
| ------ | ---- |
| POST | `/skills/self` |
| PATCH | `/skills/self/{id}` |
| DELETE | `/skills/self/{id}` |

## Org skills CRUD (org_admin)

| Method | Path |
| ------ | ---- |
| POST | `/org/skills` |
| PATCH | `/org/skills/{id}` |
| DELETE | `/org/skills/{id}` |

## Base skills CRUD (instance_admin)

| Method | Path |
| ------ | ---- |
| GET | `/skills/base` |
| POST | `/skills/base` |
| PATCH | `/skills/base/{id}` |
| DELETE | `/skills/base/{id}` |

## Copy

`POST /skills/{id}/copy` — creates a `self` skill for current user with same name/body. Allowed from base, same-org org skill, own self skill, or shared self skill.

## Sharing self skills

`POST /shares` with `object_type: "skill"` — only for `scope=self` owned by sharer. Recipients see skill under `catalog: shared` (readonly). They can copy to own library.

## Related pages

- [Tasks](tasks.md)
- [Library](library.md)
- [Skills API](../api/skills.md)
