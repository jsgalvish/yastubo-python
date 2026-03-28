"""
Schemas Pydantic para endpoints de Coberturas (admin).
Equivale a CoverageCatalogController.php + PlanVersionCoverageController.php.

Skills aplicados:
  - Pydantic: Literal types, ConfigDict, response models tipados
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CoverageStatus = Literal["active", "archived"]


# ─────────────────────────── Translatable ────────────────────────────────────


class TranslatableName(BaseModel):
    es: str = Field(..., max_length=255)
    en: Optional[str] = Field(None, max_length=255)


class TranslatableText(BaseModel):
    es: Optional[str] = None
    en: Optional[str] = None


# ─────────────────────────── UnitOfMeasure ───────────────────────────────────


class UnitOut(BaseModel):
    id: int
    name: Optional[dict] = None
    description: Optional[dict] = None
    measure_type: str
    status: str

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────── Coverage ────────────────────────────────────────


class CoverageOut(BaseModel):
    id: int
    category_id: Optional[int] = None
    unit_id: Optional[int] = None
    name: Optional[dict] = None
    description: Optional[dict] = None
    status: str
    sort_order: Optional[int] = None
    unit: Optional[UnitOut] = None

    model_config = ConfigDict(from_attributes=True)


class CoverageDataResponse(BaseModel):
    data: CoverageOut


# ─────────────────────────── CoverageCategory ────────────────────────────────


class CategoryOut(BaseModel):
    id: int
    name: Optional[dict] = None
    description: Optional[dict] = None
    status: str
    sort_order: Optional[int] = None
    coverages: list[CoverageOut] = []

    model_config = ConfigDict(from_attributes=True)


class CategoryDataResponse(BaseModel):
    data: CategoryOut


class CatalogIndexResponse(BaseModel):
    categories: list[CategoryOut]
    units: list[UnitOut]


class ArchivedCategoriesResponse(BaseModel):
    data: list[CategoryOut]


# ─────────────────────────── Category requests ───────────────────────────────


class StoreCategoryRequest(BaseModel):
    name: TranslatableName
    description: Optional[TranslatableText] = None


class ReorderItem(BaseModel):
    id: int
    sort_order: int


class ReorderCoveragesRequest(BaseModel):
    items: list[ReorderItem]


# ─────────────────────────── Coverage requests ───────────────────────────────


class StoreCoverageRequest(BaseModel):
    category_id: int
    unit_id: int
    name: TranslatableName
    description: Optional[TranslatableText] = None


class UpdateCoverageRequest(BaseModel):
    category_id: Optional[int] = None
    unit_id: Optional[int] = None
    name: Optional[TranslatableName] = None
    description: Optional[TranslatableText] = None


# ─────────────────────────── PlanVersionCoverage ─────────────────────────────


class PlanVersionCoverageOut(BaseModel):
    id: int
    plan_version_id: int
    coverage_id: int
    sort_order: Optional[int] = None
    value_int: Optional[int] = None
    value_decimal: Optional[float] = None
    value_text: Optional[dict] = None
    notes: Optional[dict] = None
    coverage_name: Optional[dict] = None
    coverage_description: Optional[dict] = None
    unit_name: Optional[dict] = None
    unit_measure_type: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class PlanVersionCoverageDataResponse(BaseModel):
    data: PlanVersionCoverageOut


class AvailableCoverageItem(BaseModel):
    id: int
    name: Optional[dict] = None
    description: Optional[dict] = None
    unit_id: Optional[int] = None
    unit_name: Optional[dict] = None
    unit_measure_type: Optional[str] = None
    attached: bool = False
    plan_version_coverage_id: Optional[int] = None


class AvailableCategoryOut(BaseModel):
    id: int
    name: Optional[dict] = None
    coverages: list[AvailableCoverageItem] = []


class AvailableCoveragesResponse(BaseModel):
    data: list[AvailableCategoryOut]


class StorePlanVersionCoverageRequest(BaseModel):
    coverage_id: int


class ReorderPVCoveragesRequest(BaseModel):
    coverage_ids: list[int]


class UpdatePVCoverageValueRequest(BaseModel):
    value_int: Optional[int] = None
    value_decimal: Optional[float] = None
    value_text: Optional[TranslatableText] = None
    notes: Optional[TranslatableText] = None
