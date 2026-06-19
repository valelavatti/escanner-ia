"""Pydantic schemas for auth-session endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class UsuarioResponse(BaseModel):
    id: int
    nombre: str


class LoginRequest(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)


class LoginResponse(BaseModel):
    token: str
    usuario: UsuarioResponse
    expires_at: datetime


class MeResponse(BaseModel):
    usuario: UsuarioResponse
