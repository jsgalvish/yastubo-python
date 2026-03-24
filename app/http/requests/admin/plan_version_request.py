"""
Schemas Pydantic para endpoints de PlanVersion (admin).
Equivale a la validación de PlanVersionController.php + PlanVersionAgeSurchargeController.php.

Skills aplicados:
  - Pydantic: Literal types, ConfigDict, schema separation
  - FastAPI: response models tipados
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PlanVersionStatus = Literal["inactive", "active", "archived"]


# ─────────────────────────── PlanVersion output ──────────────────────────────


class PlanVersionOut(BaseModel):
    """Representación de una versión de plan en respuestas API."""
    id: int
    product_id: int
    name: str
    status: str
    max_entry_age: Optional[int] = None
    max_renewal_age: Optional[int] = None
    wtime_suicide: Optional[int] = None
    wtime_preexisting_conditions: Optional[int] = None
    wtime_accident: Optional[int] = None
    country_id: Optional[int] = None
    zone_id: Optional[int] = None
    price_1: Optional[float] = None
    price_2: Optional[float] = None
    price_3: Optional[float] = None
    price_4: Optional[float] = None
    terms_file_es_id: Optional[int] = None
    terms_file_en_id: Optional[int] = None
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
    name: Optional[str] = Field(None, max_length=255)
    status: Optional[PlanVersionStatus] = None
    max_entry_age: Optional[int] = Field(None, ge=0)
    max_renewal_age: Optional[int] = Field(None, ge=0)
    wtime_suicide: Optional[int] = Field(None, ge=0)
    wtime_preexisting_conditions: Optional[int] = Field(None, ge=0)
    wtime_accident: Optional[int] = Field(None, ge=0)
    country_id: Optional[int] = None
    zone_id: Optional[int] = None
    price_1: Optional[float] = Field(None, ge=0)
    price_2: Optional[float] = Field(None, ge=0)
    price_3: Optional[float] = Field(None, ge=0)
    price_4: Optional[float] = Field(None, ge=0)
    terms_file_es_id: Optional[int] = None
    terms_file_en_id: Optional[int] = None


# ─────────────────────────── Terms HTML ──────────────────────────────────────


class TermsHtmlOut(BaseModel):
    es: Optional[str] = None
    en: Optional[str] = None


class TermsHtmlDataResponse(BaseModel):
    data: dict  # { terms_html: { es, en } }


class UpdateTermsHtmlRequest(BaseModel):
    locale: Literal["es", "en"]
    html: Optional[str] = None


# ─────────────────────────── AgeSurcharge ────────────────────────────────────


class AgeSurchargeOut(BaseModel):
    id: int
    plan_version_id: int
    age_from: Optional[int] = None
    age_to: Optional[int] = None
    surcharge_percent: Optional[float] = None

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
    age_from: Optional[int] = Field(None, ge=0)
    age_to: Optional[int] = Field(None, ge=0)
    surcharge_percent: Optional[float] = None


class UpdateAgeSurchargeRequest(BaseModel):
    age_from: Optional[int] = Field(None, ge=0)
    age_to: Optional[int] = Field(None, ge=0)
    surcharge_percent: Optional[float] = None
