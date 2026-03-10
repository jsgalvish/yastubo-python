from __future__ import annotations

import json as _json
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ── Requests ──────────────────────────────────────────────────────────────────


class StoreRoleRequest(BaseModel):
    name: str = Field(..., max_length=255)
    label: Optional[dict] = None
    scope: Optional[str] = Field(None, max_length=50)


class UpdateRoleRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    label: Optional[dict] = None
    scope: Optional[str] = Field(None, max_length=50)


class StorePermissionRequest(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class UpdatePermissionRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class ToggleAssignmentRequest(BaseModel):
    role_id: int
    permission_id: int
    value: bool


# ── Responses ─────────────────────────────────────────────────────────────────


class RoleOut(BaseModel):
    id: int
    name: str
    guard_name: str
    scope: Optional[str] = None
    level: Optional[int] = None
    label: Optional[Any] = None

    model_config = {"from_attributes": True}

    @field_validator("label", mode="before")
    @classmethod
    def parse_label(cls, v: Any) -> Any:
        """Deserializa el JSON string almacenado en la columna Text."""
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except (_json.JSONDecodeError, ValueError):
                return v
        return v


class PermissionOut(BaseModel):
    id: int
    name: str
    guard_name: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class MatrixDataOut(BaseModel):
    roles: list[RoleOut]
    permissions: list[PermissionOut]
    matrix: dict[int, list[int]]


class ToggleOut(BaseModel):
    message: str
