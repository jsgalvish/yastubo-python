"""
Schemas Pydantic para endpoints de Templates (admin).
Equivale a TemplateController.php + TemplateVersionController.php.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

TemplateType = Literal["html", "pdf"]


# ─────────────────────────── Template ────────────────────────────────────────


class TemplateOut(BaseModel):
    id: int
    name: str
    slug: str
    type: str
    test_data_json: Optional[str] = None
    active_template_version_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class VersionOut(BaseModel):
    id: int
    template_id: int
    name: str
    content: Optional[str] = None
    test_data_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TemplateDataResponse(BaseModel):
    data: dict  # {template: TemplateOut}


class TemplateShowResponse(BaseModel):
    data: dict  # {template: ..., versions: [...]}


class VersionDataResponse(BaseModel):
    data: dict  # {version: VersionOut}


class TemplateIndexResponse(BaseModel):
    data: list[TemplateOut]


# ─────────────────────────── Requests ────────────────────────────────────────


class StoreTemplateRequest(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255)
    type: TemplateType


class UpdateTemplateBasicRequest(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255)


class UpdateTestDataRequest(BaseModel):
    test_data_json: Optional[str] = None


class StoreVersionRequest(BaseModel):
    content: Optional[str] = None


class UpdateVersionBasicRequest(BaseModel):
    name: str = Field(..., max_length=255)
    content: str
