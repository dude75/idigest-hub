"""Округление денег вниз до сотых (ТЗ §10)."""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal, InvalidOperation

TWOPLACES = Decimal("0.01")
MIN_USAGE_CHARGE = Decimal("0.01")


def floor_to_cents(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_DOWN)


def usage_charge_amount(raw: Decimal) -> Decimal:
    """Списание за usage: floor до центов; при положительном raw ниже 1 цента — минимум 0.01."""
    if raw <= 0:
        return Decimal("0.00")
    floored = floor_to_cents(raw)
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
    return amount.quantize(TWOPLACES, rounding=ROUND_DOWN)


def money_str(value: Decimal) -> str:
    return format(floor_to_cents(value), "f")


def rate_str(value: Decimal) -> str:
    """Ставка тарифа (до 6 знаков): без лишних нулей в конце, напр. 0.01 вместо 0.010000."""
    return format(value.normalize(), "f")
