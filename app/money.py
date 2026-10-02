"""Округление денег вниз до сотых (ТЗ §10)."""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal, InvalidOperation

TWOPLACES = Decimal("0.01")


def floor_to_cents(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_DOWN)


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
