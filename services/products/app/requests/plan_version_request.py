"""
Schemas Pydantic para endpoints de PlanVersion (admin).
Equivale a la validación de PlanVersionController.php + PlanVersionAgeSurchargeController.php.

Skills aplicados:
  - Pydantic: Literal types, ConfigDict, schema separation
  - FastAPI: response models tipados
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PlanVersionStatus = Literal["inactive", "active", "archived"]


# ─────────────────────────── PlanVersion output ──────────────────────────────


class PlanVersionOut(BaseModel):
    """Representación de una versión de plan en respuestas API."""

    id: int
    product_id: int
    name: str
    status: str
    max_entry_age: int | None = None
    max_renewal_age: int | None = None
    wtime_suicide: int | None = None
    wtime_preexisting_conditions: int | None = None
    wtime_accident: int | None = None
    country_id: int | None = None
    zone_id: int | None = None
    price_1: float | None = None
    price_2: float | None = None
    price_3: float | None = None
    price_4: float | None = None
    terms_file_es_id: int | None = None
    terms_file_en_id: int | None = None
    can_be_activated: bool = True
    is_in_use: bool = False
    is_deletable: bool = True

    model_config = ConfigDict(from_attributes=True)


class PlanVersionDataResponse(BaseModel):
    data: PlanVersionOut


class PlanVersionDataToastResponse(BaseModel):
    data: PlanVersionOut
    toast: dict


class PlanVersionIndexResponse(BaseModel):
    data: list[PlanVersionOut]


class PlanVersionDeleteResponse(BaseModel):
    message: str


# ─────────────────────────── PlanVersion requests ────────────────────────────


class StorePlanVersionRequest(BaseModel):
    """Request para crear una versión de plan."""

    name: str = Field(..., max_length=255)


class ClonePlanVersionRequest(BaseModel):
    """Request para clonar una versión de plan."""

    name: str = Field(..., max_length=255)


class UpdatePlanVersionRequest(BaseModel):
    """Request para actualizar una versión de plan (parcial)."""

    name: str | None = Field(None, max_length=255)
    status: PlanVersionStatus | None = None
    max_entry_age: int | None = Field(None, ge=0)
    max_renewal_age: int | None = Field(None, ge=0)
    wtime_suicide: int | None = Field(None, ge=0)
    wtime_preexisting_conditions: int | None = Field(None, ge=0)
    wtime_accident: int | None = Field(None, ge=0)
    country_id: int | None = None
    zone_id: int | None = None
    price_1: float | None = Field(None, ge=0)
    price_2: float | None = Field(None, ge=0)
    price_3: float | None = Field(None, ge=0)
    price_4: float | None = Field(None, ge=0)
    terms_file_es_id: int | None = None
    terms_file_en_id: int | None = None


# ─────────────────────────── Terms HTML ──────────────────────────────────────


class TermsHtmlOut(BaseModel):
    es: str | None = None
    en: str | None = None


class TermsHtmlDataResponse(BaseModel):
    data: dict  # { terms_html: { es, en } }


class UpdateTermsHtmlRequest(BaseModel):
    locale: Literal["es", "en"]
    html: str | None = None


# ─────────────────────────── AgeSurcharge ────────────────────────────────────


class AgeSurchargeOut(BaseModel):
    id: int
    plan_version_id: int
    age_from: int | None = None
    age_to: int | None = None
    surcharge_percent: float | None = None

    model_config = ConfigDict(from_attributes=True)


class AgeSurchargeDataResponse(BaseModel):
    data: AgeSurchargeOut
    toast: dict


class AgeSurchargeIndexResponse(BaseModel):
    data: list[AgeSurchargeOut]


class AgeSurchargeDeleteResponse(BaseModel):
    id: int
    message: str


class StoreAgeSurchargeRequest(BaseModel):
    age_from: int | None = Field(None, ge=0)
    age_to: int | None = Field(None, ge=0)
    surcharge_percent: float | None = None


class UpdateAgeSurchargeRequest(BaseModel):
    age_from: int | None = Field(None, ge=0)
    age_to: int | None = Field(None, ge=0)
    surcharge_percent: float | None = None
