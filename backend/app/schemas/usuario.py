"""Pydantic schemas for user management endpoints."""

from typing import Optional

from pydantic import BaseModel, Field


class DepositoAssignment(BaseModel):
    deposito_id: int
    deposito_nombre: str
    role: str


class UsuarioCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)
    is_admin: bool = False


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=1)
    is_admin: Optional[bool] = None


class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    is_admin: bool


class UsuarioWithDepositos(UsuarioResponse):
    depositos: list[DepositoAssignment] = []


class DepositoAssignRequest(BaseModel):
    deposito_id: int
    role: str = Field(..., pattern=r"^(admin|operator|viewer)$")
