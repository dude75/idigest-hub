"""Impact preview before deleting a tariff."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Organization, Tariff
from app.timeutil import utcnow


def _tariff_choice(tariff: Tariff) -> dict[str, str]:
    return {"id": tariff.id, "name": tariff.name}


def _replacement_options(db: Session, *, exclude_id: str) -> tuple[dict[str, str] | None, list[dict[str, str]]]:
    rows = db.scalars(
        select(Tariff)
        .where(Tariff.id != exclude_id, Tariff.archived_at.is_(None))
        .order_by(Tariff.created_at)
    ).all()
    available = [_tariff_choice(row) for row in rows]
    if not available:
        return None, []
    signup = next((row for row in rows if row.available_on_signup), None)
    if signup is not None:
        return _tariff_choice(signup), available
    return _tariff_choice(rows[0]), available


def compute_tariff_delete_impact(db: Session, tariff: Tariff) -> dict[str, Any]:
    total = int(db.scalar(select(func.count()).select_from(Tariff)) or 0)
    last_tariff = total <= 1
    org_count = int(
        db.scalar(select(func.count()).select_from(Organization).where(Organization.tariff_id == tariff.id)) or 0
    )
    affected_orgs = [
        {"id": row.id, "name": row.name}
        for row in db.scalars(
            select(Organization).where(Organization.tariff_id == tariff.id).order_by(Organization.name)
        ).all()
    ]
    suggested, available = _replacement_options(db, exclude_id=tariff.id)
    can_remediate = bool(org_count and available)
    blocking = bool(last_tariff or (org_count and not available))
    return {
        "tariff": {"id": tariff.id, "name": tariff.name, "archived": tariff.archived_at is not None},
        "last_tariff": last_tariff,
        "org_count": org_count,
        "affected_orgs": affected_orgs,
        "available_tariffs": available,
        "suggested_replacement": suggested,
        "can_remediate": can_remediate,
        "blocking": blocking,
    }


def apply_tariff_remediation(db: Session, *, from_tariff_id: str, replacement_tariff_id: str) -> dict[str, int]:
    replacement = db.get(Tariff, replacement_tariff_id)
    if replacement is None or replacement.id == from_tariff_id or replacement.archived_at is not None:
        raise ValueError("invalid_replacement")
    orgs_updated = 0
    for org in db.scalars(select(Organization).where(Organization.tariff_id == from_tariff_id)).all():
        org.tariff_id = replacement.id
        org.updated_at = utcnow()
        orgs_updated += 1
    db.flush()
    return {"orgs_updated": orgs_updated}
