"""Tariff admin API response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import OkStatusResponse


class TariffChoice(BaseModel):
    id: str
    name: str


class TariffDeleteImpactTariff(BaseModel):
    id: str
    name: str
    archived: bool


class TariffDeleteImpactResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tariff: TariffDeleteImpactTariff
    last_tariff: bool
    org_count: int
    affected_orgs: list[TariffChoice] = Field(default_factory=list)
    available_tariffs: list[TariffChoice] = Field(default_factory=list)
    suggested_replacement: TariffChoice | None = None
    can_remediate: bool
    blocking: bool


class TariffDeleteResponse(OkStatusResponse):
    remediation: dict[str, int] | None = None
