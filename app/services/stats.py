"""Счётчики завершённых задач и длительности аудио для дашбордов."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Task, UsageEvent, User
from app.money import money_str, parse_money
from app.timeutil import as_utc


def completed_job_stats(db: Session, *, org_id: str | None = None) -> dict:
    task_filters = []
    if org_id is not None:
        task_filters.append(Task.org_id == org_id)
    transcribe_done = int(
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.type == "transcribe", Task.status == "success", *task_filters)
        )
        or 0
    )
    summarize_done = int(
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.type == "summarize", Task.status == "success", *task_filters)
        )
        or 0
    )
    audio_query = (
        select(func.coalesce(func.sum(UsageEvent.audio_sec), 0))
        .select_from(UsageEvent)
        .join(Task, Task.id == UsageEvent.task_id)
        .where(Task.type == "transcribe", Task.status == "success")
    )
    if org_id is not None:
        audio_query = audio_query.where(Task.org_id == org_id)
    audio_sec = db.scalar(audio_query)
    return {
        "tasks_transcribe_success": transcribe_done,
        "tasks_summarize_success": summarize_done,
        "audio_transcribed_sec": float(audio_sec or 0),
    }


def _parse_day_start(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if "T" in text:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return as_utc(parsed)
    day = datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return day


def usage_stats(
    db: Session,
    *,
    org_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: str | None = None,
    kind: str | None = None,
) -> dict:
    filters = []
    if org_id is not None:
        filters.append(UsageEvent.org_id == org_id)
    if start is not None:
        filters.append(UsageEvent.created_at >= start)
    if end is not None:
        filters.append(UsageEvent.created_at < end)
    if user_id:
        filters.append(UsageEvent.user_id == user_id)
    if kind in {"transcribe", "summarize"}:
        filters.append(UsageEvent.kind == kind)

    rows = list(db.scalars(select(UsageEvent).where(*filters).order_by(UsageEvent.created_at)).all())
    transcribe_done = 0
    summarize_done = 0
    audio_sec = 0.0
    summary_chars = 0
    total = Decimal("0.00")
    by_day: dict[str, dict] = {}

    for event in rows:
        if event.kind == "transcribe":
            transcribe_done += 1
            audio_sec += float(event.audio_sec or 0)
        elif event.kind == "summarize":
            summarize_done += 1
            summary_chars += int(event.summary_chars or 0)
        total += Decimal(event.amount)
        day_key = as_utc(event.created_at).date().isoformat()
        bucket = by_day.setdefault(
            day_key,
            {
                "date": day_key,
                "tasks_transcribe_success": 0,
                "tasks_summarize_success": 0,
                "audio_transcribed_sec": 0.0,
                "summary_chars": 0,
                "amount": Decimal("0.00"),
            },
        )
        if event.kind == "transcribe":
            bucket["tasks_transcribe_success"] += 1
            bucket["audio_transcribed_sec"] += float(event.audio_sec or 0)
        elif event.kind == "summarize":
            bucket["tasks_summarize_success"] += 1
            bucket["summary_chars"] += int(event.summary_chars or 0)
        bucket["amount"] += Decimal(event.amount)

    days = []
    for key in sorted(by_day):
        bucket = by_day[key]
        days.append(
            {
                "date": bucket["date"],
                "tasks_transcribe_success": bucket["tasks_transcribe_success"],
                "tasks_summarize_success": bucket["tasks_summarize_success"],
                "audio_transcribed_sec": bucket["audio_transcribed_sec"],
                "summary_chars": bucket["summary_chars"],
                "amount": money_str(bucket["amount"]),
            }
        )
    return {
        "tasks_transcribe_success": transcribe_done,
        "tasks_summarize_success": summarize_done,
        "audio_transcribed_sec": audio_sec,
        "summary_chars": summary_chars,
        "total_amount": money_str(total),
        "days": days,
    }


def org_usage_stats(
    db: Session,
    org_id: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: str | None = None,
    kind: str | None = None,
) -> dict:
    return usage_stats(
        db,
        org_id=org_id,
        start=start,
        end=end,
        user_id=user_id,
        kind=kind,
    )


def parse_org_stats_range(from_day: str | None, to_day: str | None) -> tuple[datetime | None, datetime | None]:
    start = _parse_day_start(from_day)
    end = _parse_day_start(to_day)
    if end is not None and end.hour == 0 and end.minute == 0 and end.second == 0 and "T" not in (to_day or ""):
        end = end + timedelta(days=1)
    return start, end


def org_ledger(
    db: Session,
    org_id: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: str | None = None,
    kind: str | None = None,
) -> dict:
    entries: list[dict] = []
    user_cache: dict[str, str | None] = {}
    total_spent = Decimal("0.00")
    total_topup = Decimal("0.00")
    net = Decimal("0.00")

    usage_filters = [UsageEvent.org_id == org_id]
    if start is not None:
        usage_filters.append(UsageEvent.created_at >= start)
    if end is not None:
        usage_filters.append(UsageEvent.created_at < end)
    if user_id:
        usage_filters.append(UsageEvent.user_id == user_id)
    if kind in {"transcribe", "summarize"}:
        usage_filters.append(UsageEvent.kind == kind)

    for event in db.scalars(select(UsageEvent).where(*usage_filters)).all():
        if event.user_id not in user_cache:
            user = db.get(User, event.user_id)
            user_cache[event.user_id] = user.email if user else None
        usage_amount = Decimal(event.amount)
        impact = Decimal("0.00") if event.unlimited_skip else -usage_amount
        total_spent += -impact
        net += impact
        entries.append(
            {
                "id": event.id,
                "entry_type": "charge",
                "created_at": as_utc(event.created_at).isoformat(),
                "amount": money_str(impact),
                "usage_amount": money_str(usage_amount),
                "kind": event.kind,
                "user_id": event.user_id,
                "user_email": user_cache[event.user_id],
                "task_id": event.task_id,
                "actor_email": None,
                "unlimited_skip": event.unlimited_skip,
                "audio_sec": event.audio_sec,
                "summary_chars": event.summary_chars,
            }
        )

    if not user_id and kind not in {"transcribe", "summarize"}:
        audit_filters = [AuditLog.action == "wallet.delta"]
        if start is not None:
            audit_filters.append(AuditLog.created_at >= start)
        if end is not None:
            audit_filters.append(AuditLog.created_at < end)
        for row in db.scalars(select(AuditLog).where(*audit_filters)).all():
            payload = row.payload_json or {}
            if payload.get("org_id") != org_id:
                continue
            delta = parse_money(str(payload.get("delta", "0")))
            actor_email = None
            if row.actor_user_id:
                actor = db.get(User, row.actor_user_id)
                actor_email = actor.email if actor else None
            if delta > 0:
                total_topup += delta
            net += delta
            entries.append(
                {
                    "id": row.id,
                    "entry_type": "wallet",
                    "created_at": as_utc(row.created_at).isoformat(),
                    "amount": money_str(delta),
                    "usage_amount": None,
                    "kind": None,
                    "user_id": None,
                    "user_email": None,
                    "task_id": None,
                    "actor_email": actor_email,
                    "unlimited_skip": False,
                    "audio_sec": None,
                    "summary_chars": None,
                }
            )

    entries.sort(key=lambda row: row["created_at"], reverse=True)
    return {
        "items": entries,
        "total_spent": money_str(total_spent),
        "total_topup": money_str(total_topup),
        "net": money_str(net),
    }
