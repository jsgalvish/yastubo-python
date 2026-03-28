"""
Schemas Pydantic para endpoints de PlanVersionCountry y
PlanVersionRepatriationCountry (admin).

Equivale a la validación de PlanVersionCountryController.php
y PlanVersionRepatriationCountryController.php.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────── Country output ────────────────────────────────


class PlanCountryOut(BaseModel):
    """País asociado a una versión de plan (con precio)."""
    id: int
    name: dict
    iso2: Optional[str] = None
    iso3: Optional[str] = None
    continent_code: str
    continent_label: str
    phone_code: Optional[str] = None
    is_active: bool
    price: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ModalCountryOut(BaseModel):
    """País para el modal de selección (con flag attached y precio)."""
    id: int
    name: dict
    iso2: Optional[str] = None
    iso3: Optional[str] = None
    continent_code: str
    continent_label: str
    phone_code: Optional[str] = None
    is_active: bool
    attached: bool = False
    price: Optional[float] = None

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
    message: Optional[str] = None
    data: Optional[dict] = None


class CountryDataToastResponse(BaseModel):
    toast: dict
    data: dict


# ─────────────────────────── Repatriation country output ───────────────────


class RepatriationCountryOut(BaseModel):
    """País de repatriación (sin precio)."""
    id: int
    name: dict
    iso2: Optional[str] = None
    iso3: Optional[str] = None
    continent_code: str
    continent_label: str
    phone_code: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class RepatriationModalCountryOut(BaseModel):
    """País para modal de repatriación (con flag attached)."""
    id: int
    name: dict
    iso2: Optional[str] = None
    iso3: Optional[str] = None
    continent_code: str
    continent_label: str
    phone_code: Optional[str] = None
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
    price: Optional[float] = None


class DetachByZoneRequest(BaseModel):
    """Request para desasociar los países de una zona."""
    zone_id: int
