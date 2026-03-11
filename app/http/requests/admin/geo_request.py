"""
Schemas Pydantic para endpoints de Countries y Zones (admin).
Equivale a StoreCountryRequest, UpdateCountryRequest,
StoreZoneRequest, UpdateZoneRequest en PHP.
"""
from __future__ import annotations

import json as _json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from config.continents import CONTINENTS

_CONTINENT_KEYS = set(CONTINENTS.keys())


# ─────────────────────────── Country Schemas ─────────────────────────────────


class TranslatableNameIn(BaseModel):
    """Nombre traducible: {es, en}."""

    es: str = Field(..., max_length=255)
    en: str = Field(..., max_length=255)


class StoreCountryRequest(BaseModel):
    name: TranslatableNameIn
    iso2: str = Field(..., min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    iso3: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    continent_code: str = Field(..., min_length=2, max_length=2)
    phone_code: Optional[str] = Field(None, max_length=10)

    @field_validator("continent_code")
    @classmethod
    def validate_continent(cls, v: str) -> str:
        if v not in _CONTINENT_KEYS:
            raise ValueError(f"Continente inválido. Valores permitidos: {sorted(_CONTINENT_KEYS)}")
        return v

    @field_validator("phone_code")
    @classmethod
    def validate_phone_code(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[0-9]+$", v):
            raise ValueError("El código telefónico debe contener solo dígitos.")
        return v

    @model_validator(mode="after")
    def uppercase_iso(self) -> "StoreCountryRequest":
        self.iso2 = self.iso2.upper()
        self.iso3 = self.iso3.upper()
        return self


class UpdateCountryRequest(BaseModel):
    name: TranslatableNameIn
    iso2: str = Field(..., min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    iso3: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    continent_code: str = Field(..., min_length=2, max_length=2)
    phone_code: Optional[str] = Field(None, max_length=10)

    @field_validator("continent_code")
    @classmethod
    def validate_continent(cls, v: str) -> str:
        if v not in _CONTINENT_KEYS:
            raise ValueError(f"Continente inválido. Valores permitidos: {sorted(_CONTINENT_KEYS)}")
        return v

    @field_validator("phone_code")
    @classmethod
    def validate_phone_code(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[0-9]+$", v):
            raise ValueError("El código telefónico debe contener solo dígitos.")
        return v

    @model_validator(mode="after")
    def uppercase_iso(self) -> "UpdateCountryRequest":
        self.iso2 = self.iso2.upper()
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
    name: str = Field(..., max_length=255)
    description: Optional[str] = None


class UpdateZoneRequest(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None


class ZoneSimpleOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool = True

    model_config = {"from_attributes": True}


class ZoneOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool = True
    countries: list[CountryForZoneOut] = []
    countries_count: int = 0

    model_config = {"from_attributes": True}
