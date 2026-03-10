"""
Schemas Pydantic para endpoints de Countries y Zones (admin).
Equivale a StoreCountryRequest, UpdateCountryRequest,
StoreZoneRequest, UpdateZoneRequest en PHP.
"""
from __future__ import annotations

import json as _json
from typing import Any, Optional

from pydantic import BaseModel, field_validator, model_validator


# ─────────────────────────── Country Schemas ─────────────────────────────────

class TranslatableNameIn(BaseModel):
    """Nombre traducible: {es, en}."""
    es: str
    en: Optional[str] = None


class StoreCountryRequest(BaseModel):
    name: TranslatableNameIn
    iso2: str
    iso3: str
    continent_code: str
    phone_code: Optional[str] = None

    @model_validator(mode="after")
    def uppercase_iso(self) -> "StoreCountryRequest":
        self.iso2 = self.iso2.upper()
        self.iso3 = self.iso3.upper()
        return self


class UpdateCountryRequest(BaseModel):
    name: Optional[TranslatableNameIn] = None
    iso2: Optional[str] = None
    iso3: Optional[str] = None
    continent_code: Optional[str] = None
    phone_code: Optional[str] = None

    @model_validator(mode="after")
    def uppercase_iso(self) -> "UpdateCountryRequest":
        if self.iso2 is not None:
            self.iso2 = self.iso2.upper()
        if self.iso3 is not None:
            self.iso3 = self.iso3.upper()
        return self


class CountryOut(BaseModel):
    id: int
    name: Optional[Any] = None
    iso2: Optional[str] = None
    iso3: Optional[str] = None
    continent_code: Optional[str] = None
    continent_label: Optional[str] = None
    phone_code: Optional[str] = None
    is_active: bool = True

    model_config = {"from_attributes": True}

    @field_validator("name", mode="before")
    @classmethod
    def parse_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except Exception:
                return v
        return v


class CountryForZoneOut(BaseModel):
    """Resumen de país en respuestas de zona."""
    id: int
    name: Optional[Any] = None
    continent_code: Optional[str] = None
    continent_label: Optional[str] = None
    phone_code: Optional[str] = None
    is_active: bool = True

    model_config = {"from_attributes": True}

    @field_validator("name", mode="before")
    @classmethod
    def parse_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except Exception:
                return v
        return v


class CountryAvailableOut(CountryForZoneOut):
    """País con bandera 'attached' para endpoint availableCountries."""
    attached: bool = False


# ─────────────────────────── Zone Schemas ────────────────────────────────────

class StoreZoneRequest(BaseModel):
    name: str
    description: Optional[str] = None


class UpdateZoneRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ZoneOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool = True
    countries: list[CountryForZoneOut] = []
    countries_count: int = 0

    model_config = {"from_attributes": True}
