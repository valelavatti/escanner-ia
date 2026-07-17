"""Pydantic schemas for depositos (warehouses)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DepositoResponse(BaseModel):
    id: int
    nombre: str


class DepositoWithStats(DepositoResponse):
    """Deposito with estantes/usuarios counts (used by GET /depositos)."""

    created_at: Optional[datetime] = None
    estantes_count: int = 0
    usuarios_count: int = 0


class DepositoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)


class DepositoUpdate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
