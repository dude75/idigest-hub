"""Округление денег вниз до тысячных (ТЗ §10)."""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal, InvalidOperation

MONEY_QUANT = Decimal("0.001")
MIN_USAGE_CHARGE = Decimal("0.001")


def floor_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_DOWN)


# Back-compat alias for callers/docs migrating from cent precision.
floor_to_cents = floor_money


def usage_charge_amount(raw: Decimal) -> Decimal:
    """Списание за usage: floor до тысячных; при положительном raw ниже 0.001 — минимум 0.001."""
    if raw <= 0:
        return Decimal("0.000")
    floored = floor_money(raw)
    if floored > 0:
        return floored
    return MIN_USAGE_CHARGE


def parse_money(value: str | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        amount = value
    else:
        text = value.strip()
        if not text:
            raise InvalidOperation
        try:
            amount = Decimal(text)
        except InvalidOperation:
            raise
    return amount.quantize(MONEY_QUANT, rounding=ROUND_DOWN)


def money_str(value: Decimal) -> str:
    return format(floor_money(value), "f")


def rate_str(value: Decimal) -> str:
    """Ставка тарифа (до 6 знаков): без лишних нулей в конце, напр. 0.01 вместо 0.010000."""
    return format(value.normalize(), "f")
