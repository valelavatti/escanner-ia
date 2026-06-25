"""Pydantic schemas for auth-session endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class DepositoAssignment(BaseModel):
    deposito_id: int
    deposito_nombre: str
    role: str


class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    is_admin: bool = False


class UsuarioWithDepositos(UsuarioResponse):
    depositos: list[DepositoAssignment] = []


class LoginRequest(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    token: str
    usuario: UsuarioResponse
    expires_at: datetime


class MeResponse(BaseModel):
    usuario: UsuarioResponse
    depositos: list[DepositoAssignment]
