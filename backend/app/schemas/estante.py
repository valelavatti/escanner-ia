"""Pydantic schemas for estantes and ubicaciones."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EstanteCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=50)
    orden_visual: int = 0
    filas: int = Field(..., ge=1, le=50)
    columnas: int = Field(..., ge=1, le=50)


class EstanteUpdate(BaseModel):
    filas: Optional[int] = Field(None, ge=1, le=50)
    columnas: Optional[int] = Field(None, ge=1, le=50)
    orden_visual: Optional[int] = None


class EstanteResponse(BaseModel):
    id: int
    nombre: str
    orden_visual: int
    filas: int
    columnas: int
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    ubicaciones_count: int = 0


class UbicacionResponse(BaseModel):
    id: int
    estante_id: int
    estante_nombre: str
    fila: int
    columna: int
    producto_id: Optional[str] = None
    producto_sku: Optional[str] = None
    producto_descripcion: Optional[str] = None
    stock_actual: int
    qr_valor: str
    estado: str


class UbicacionAssignRequest(BaseModel):
    producto_id: str = Field(..., min_length=1)


class EstanteUpdateResponse(BaseModel):
    estante: EstanteResponse
    out_of_bounds: list[UbicacionResponse]


class ConfirmDeleteOutOfBoundsRequest(BaseModel):
    ubicacion_ids: list[int]


class EstanteDetailResponse(EstanteResponse):
    ubicaciones: list[UbicacionResponse]
