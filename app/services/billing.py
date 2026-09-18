"""Кошелёк и снимок тарифа на задачу (ТЗ §10)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.constants import MAX_UPLOAD_BYTES_CAP
from app.deps import AuthContext
from app.errors import ApiError, ErrorCode
from app.i18n import t
from app.models import Organization, Tariff, Task, UsageEvent, new_id
from app.money import floor_to_cents
from app.timeutil import utcnow


def upload_limit(tariff: Tariff) -> int:
    return min(int(tariff.max_upload_bytes), MAX_UPLOAD_BYTES_CAP)


def assert_can_accept_task(ctx: AuthContext, org: Organization, locale: str) -> Tariff:
    tariff = org.tariff
    if not tariff.unlimited and org.balance <= 0:
        raise ApiError(
            ErrorCode.insufficient_balance,
            t(locale, ErrorCode.insufficient_balance.value),
        )
    return tariff


def snapshot_fields(tariff: Tariff, asr_model: str | None, diarization_model: str | None) -> dict:
    return {
        "snap_unlimited": tariff.unlimited,
        "snap_price_per_audio_sec": tariff.price_per_audio_sec,
        "snap_price_per_summarize_job": tariff.price_per_summarize_job,
        "snap_price_per_1k_summary_chars": tariff.price_per_1k_summary_chars,
        "snap_max_upload_bytes": upload_limit(tariff),
        "snap_asr_model": asr_model,
        "snap_diarization_model": diarization_model,
    }


def transcribe_amount(task: Task, audio_duration_sec: float) -> Decimal:
    raw = Decimal(str(audio_duration_sec)) * Decimal(task.snap_price_per_audio_sec)
    return floor_to_cents(raw)


def summary_char_units(length: int) -> int:
    if length <= 0:
        return 0
    return (length + 999) // 1000


def summarize_amount(task: Task, body: str) -> Decimal:
    job = floor_to_cents(Decimal(task.snap_price_per_summarize_job))
    units = summary_char_units(len(body))
    text = floor_to_cents(Decimal(units) * Decimal(task.snap_price_per_1k_summary_chars))
    return job + text


def signup_balance(tariff: Tariff) -> Decimal:
    if tariff.unlimited:
        return Decimal("0.00")
    return floor_to_cents(Decimal(tariff.signup_credit))


def org_api_enabled(org: Organization | None) -> bool:
    if org is None:
        return True
    return bool(org.tariff.api_enabled)


def apply_success_charge(
    db: Session,
    task: Task,
    org: Organization,
    *,
    audio_sec: float | None,
    amount: Decimal,
    summary_chars: int | None = None,
) -> None:
    if task.billed:
        return
    skip = bool(task.snap_unlimited)
    if not skip:
        org.balance = floor_to_cents(Decimal(org.balance) - amount)
        org.updated_at = utcnow()
    db.add(
        UsageEvent(
            id=new_id(),
            org_id=task.org_id,
            user_id=task.user_id,
            task_id=task.id,
            kind=task.type,
            audio_sec=audio_sec,
            summary_chars=summary_chars,
            amount=amount,
            unlimited_skip=skip,
            created_at=utcnow(),
        )
    )
    task.billed = True
