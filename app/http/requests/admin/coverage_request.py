"""
Schemas Pydantic para endpoints de Coberturas (admin).
Equivale a CoverageCatalogController.php + PlanVersionCoverageController.php.

Skills aplicados:
  - Pydantic: Literal types, ConfigDict, response models tipados
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CoverageStatus = Literal["active", "archived"]


# ─────────────────────────── Translatable ────────────────────────────────────


class TranslatableName(BaseModel):
    es: str = Field(..., max_length=255)
    en: str | None = Field(None, max_length=255)


class TranslatableText(BaseModel):
    es: str | None = None
    en: str | None = None


# ─────────────────────────── UnitOfMeasure ───────────────────────────────────


class UnitOut(BaseModel):
    id: int
    name: dict | None = None
    description: dict | None = None
    measure_type: str
    status: str

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────── Coverage ────────────────────────────────────────


class CoverageOut(BaseModel):
    id: int
    category_id: int | None = None
    unit_id: int | None = None
    name: dict | None = None
    description: dict | None = None
    status: str
    sort_order: int | None = None
    unit: UnitOut | None = None

    model_config = ConfigDict(from_attributes=True)


class CoverageDataResponse(BaseModel):
    data: CoverageOut


# ─────────────────────────── CoverageCategory ────────────────────────────────


class CategoryOut(BaseModel):
    id: int
    name: dict | None = None
    description: dict | None = None
    status: str
    sort_order: int | None = None
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
    description: TranslatableText | None = None


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
    description: TranslatableText | None = None


class UpdateCoverageRequest(BaseModel):
    category_id: int | None = None
    unit_id: int | None = None
    name: TranslatableName | None = None
    description: TranslatableText | None = None


# ─────────────────────────── PlanVersionCoverage ─────────────────────────────


class PlanVersionCoverageOut(BaseModel):
    id: int
    plan_version_id: int
    coverage_id: int
    sort_order: int | None = None
    value_int: int | None = None
    value_decimal: float | None = None
    value_text: dict | None = None
    notes: dict | None = None
    coverage_name: dict | None = None
    coverage_description: dict | None = None
    unit_name: dict | None = None
    unit_measure_type: str | None = None
    category_id: int | None = None
    category_name: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class PlanVersionCoverageDataResponse(BaseModel):
    data: PlanVersionCoverageOut


class AvailableCoverageItem(BaseModel):
    id: int
    name: dict | None = None
    description: dict | None = None
    unit_id: int | None = None
    unit_name: dict | None = None
    unit_measure_type: str | None = None
    attached: bool = False
    plan_version_coverage_id: int | None = None


class AvailableCategoryOut(BaseModel):
    id: int
    name: dict | None = None
    coverages: list[AvailableCoverageItem] = []


class AvailableCoveragesResponse(BaseModel):
    data: list[AvailableCategoryOut]


class StorePlanVersionCoverageRequest(BaseModel):
    coverage_id: int


class ReorderPVCoveragesRequest(BaseModel):
    coverage_ids: list[int]


class UpdatePVCoverageValueRequest(BaseModel):
    value_int: int | None = None
    value_decimal: float | None = None
    value_text: TranslatableText | None = None
    notes: TranslatableText | None = None
