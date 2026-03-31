"""
Schemas Pydantic para endpoints de PlanVersionCountry y
PlanVersionRepatriationCountry (admin).

Equivale a la validación de PlanVersionCountryController.php
y PlanVersionRepatriationCountryController.php.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────── Country output ────────────────────────────────


class PlanCountryOut(BaseModel):
    """País asociado a una versión de plan (con precio)."""
    id: int
    name: dict
    iso2: str | None = None
    iso3: str | None = None
    continent_code: str
    continent_label: str
    phone_code: str | None = None
    is_active: bool
    price: float | None = None

    model_config = ConfigDict(from_attributes=True)


class ModalCountryOut(BaseModel):
    """País para el modal de selección (con flag attached y precio)."""
    id: int
    name: dict
    iso2: str | None = None
    iso3: str | None = None
    continent_code: str
    continent_label: str
    phone_code: str | None = None
    is_active: bool
    attached: bool = False
    price: float | None = None

    model_config = ConfigDict(from_attributes=True)


class ZoneOut(BaseModel):
    id: int
    name: str
    countries_count: int


# ─────────────────────────── Country index response ────────────────────────


class PlanVersionCountryIndexData(BaseModel):
    plan_countries: list[PlanCountryOut]
    countries: list[ModalCountryOut]
    zones: list[ZoneOut]
    continents: dict[str, str]


class PlanVersionCountryIndexResponse(BaseModel):
    data: PlanVersionCountryIndexData


# ─────────────────────────── Attach / detach responses ─────────────────────


class CountryListToastResponse(BaseModel):
    toast: dict
    data: dict  # { countries: [...] }


class CountryListResponse(BaseModel):
    message: str | None = None
    data: dict | None = None


class CountryDataToastResponse(BaseModel):
    toast: dict
    data: dict


# ─────────────────────────── Repatriation country output ───────────────────


class RepatriationCountryOut(BaseModel):
    """País de repatriación (sin precio)."""
    id: int
    name: dict
    iso2: str | None = None
    iso3: str | None = None
    continent_code: str
    continent_label: str
    phone_code: str | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class RepatriationModalCountryOut(BaseModel):
    """País para modal de repatriación (con flag attached)."""
    id: int
    name: dict
    iso2: str | None = None
    iso3: str | None = None
    continent_code: str
    continent_label: str
    phone_code: str | None = None
    is_active: bool
    attached: bool = False

    model_config = ConfigDict(from_attributes=True)


class RepatriationCountryIndexData(BaseModel):
    plan_countries: list[RepatriationCountryOut]
    countries: list[RepatriationModalCountryOut]
    zones: list[ZoneOut]
    continents: dict[str, str]


class RepatriationCountryIndexResponse(BaseModel):
    data: RepatriationCountryIndexData


# ─────────────────────────── Requests ──────────────────────────────────────


class AttachCountriesRequest(BaseModel):
    """Request para asociar países."""
    country_ids: list[int] = Field(default_factory=list)


class AttachZoneRequest(BaseModel):
    """Request para asociar todos los países de una zona."""
    zone_id: int


class UpdateCountryPriceRequest(BaseModel):
    """Request para actualizar el precio de un país."""
    price: float | None = None


class DetachByZoneRequest(BaseModel):
    """Request para desasociar los países de una zona."""
    zone_id: int
