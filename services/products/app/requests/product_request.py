"""
Schemas Pydantic para endpoints de Products (admin).
Equivale a la validación inline de ProductController.php en Laravel.

Cambios aplicados por auditoría de skills:
  - HIGH-2: Response models tipados (no dict)
  - MED-6: Literal types para status y product_type
  - Pydantic skill: ConfigDict, Field constraints, schema separation
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProductStatus = Literal["active", "inactive"]
ProductType = Literal["plan_regular", "plan_capitado"]


# ─────────────────────────── Translatable helper ─────────────────────────────


class TranslatableField(BaseModel):
    """Campo traducible requerido (es obligatorio, en opcional)."""
    es: str = Field(..., max_length=255)
    en: Optional[str] = Field(None, max_length=255)


class TranslatableText(BaseModel):
    """Campo traducible opcional (ambos idiomas opcionales)."""
    es: Optional[str] = None
    en: Optional[str] = None


# ─────────────────────────── Output schemas ──────────────────────────────────


class ProductOut(BaseModel):
    """Representación de un producto en respuestas API."""
    id: int
    company_id: Optional[int] = None
    status: Optional[str] = None
    product_type: str
    show_in_widget: bool
    name: Optional[dict] = None
    description: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class ProductDataResponse(BaseModel):
    """Respuesta estándar con data de producto."""
    data: ProductOut


class ProductDataToastResponse(BaseModel):
    """Respuesta con data de producto + toast notification."""
    data: ProductOut
    toast: dict


class ProductIndexResponse(BaseModel):
    """Respuesta del listado de productos."""
    products: list[ProductOut]
    product_type_options: list[str]


# ─────────────────────────── Store request ───────────────────────────────────


class StoreProductRequest(BaseModel):
    """Request para crear un producto."""
    name: TranslatableField
    description: Optional[TranslatableText] = None
    product_type: ProductType
    show_in_widget: bool = False
    company_id: Optional[int] = None


# ─────────────────────────── Update request ──────────────────────────────────


class UpdateProductRequest(BaseModel):
    """Request para actualizar un producto (product_type y company_id inmutables)."""
    name: Optional[TranslatableField] = None
    description: Optional[TranslatableText] = None
    show_in_widget: Optional[bool] = None
    status: Optional[ProductStatus] = None
