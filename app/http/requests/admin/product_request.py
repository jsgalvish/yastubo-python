"""
Schemas Pydantic para endpoints de Products (admin).
Equivale a la validación inline de ProductController.php en Laravel.
"""
from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_VALID_STATUSES = {"active", "inactive"}
_VALID_TYPES = {"plan_regular", "plan_capitado"}


# ─────────────────────────── Translatable helper ─────────────────────────────


class TranslatableField(BaseModel):
    es: str = Field(..., max_length=255)
    en: Optional[str] = Field(None, max_length=255)


class TranslatableText(BaseModel):
    es: Optional[str] = None
    en: Optional[str] = None


# ─────────────────────────── Output schemas ──────────────────────────────────


class ProductOut(BaseModel):
    id: int
    company_id: Optional[int] = None
    status: Optional[str] = None
    product_type: str
    show_in_widget: bool
    name: Optional[dict] = None
    description: Optional[dict] = None

    model_config = {"from_attributes": True}


# ─────────────────────────── Store request ───────────────────────────────────


class StoreProductRequest(BaseModel):
    name: TranslatableField
    description: Optional[TranslatableText] = None
    product_type: str
    show_in_widget: bool = False
    company_id: Optional[int] = None

    @field_validator("product_type")
    @classmethod
    def validate_product_type(cls, v: str) -> str:
        if v not in _VALID_TYPES:
            raise ValueError(f"Tipo de producto inválido. Valores permitidos: {sorted(_VALID_TYPES)}")
        return v


# ─────────────────────────── Update request ──────────────────────────────────


class UpdateProductRequest(BaseModel):
    name: Optional[TranslatableField] = None
    description: Optional[TranslatableText] = None
    show_in_widget: Optional[bool] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(f"Estado inválido. Valores permitidos: {sorted(_VALID_STATUSES)}")
        return v
