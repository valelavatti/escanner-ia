"""Pydantic schemas for stock movements (movimientos) and audit trail."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class MovimientoCreate(BaseModel):
    """Request body to create a stock movement.

    For ``alta``, ``cantidad`` is the amount to add. For ``ajuste``,
    ``cantidad`` is the new absolute stock.
    """

    producto_sku: str = Field(..., min_length=1, description="SKU del producto")
    ubicacion_id: int = Field(..., ge=1, description="ID de la ubicacion")
    cantidad: int = Field(..., description="Cantidad para alta o stock absoluto para ajuste")
    tipo: Literal["alta", "ajuste"] = Field(default="alta", description="Tipo de movimiento")


class MovimientoResponse(BaseModel):
    """Full movement record returned by the API."""

    id: int
    usuario_id: int
    usuario_nombre: str
    producto_sku: Optional[str] = None
    producto_descripcion: Optional[str] = None
    ubicacion_id: int
    ubicacion_qr: str
    estante_nombre: str
    fila: int
    columna: int
    cantidad: int
    stock_anterior: int
    stock_nuevo: int
    timestamp: datetime
    tipo: str
    stock_general_anterior: int = Field(default=0, description="Stock general del producto ANTES de este movimiento")
    stock_general_nuevo: int = Field(default=0, description="Stock general del producto DESPUES de este movimiento")


class MovimientoListResponse(BaseModel):
    """Paginated list of movements."""

    items: list[MovimientoResponse]
    total: int


class MovimientoFilters(BaseModel):
    """Query parameters for filtering the audit trail."""

    usuario_id: Optional[int] = Field(None, description="Filtrar por ID de usuario")
    producto_sku: Optional[str] = Field(None, description="Filtrar por SKU de producto")
    ubicacion_id: Optional[int] = Field(None, description="Filtrar por ID de ubicacion")
    from_date: Optional[str] = Field(None, description="Fecha desde (ISO 8601)")
    to_date: Optional[str] = Field(None, description="Fecha hasta (ISO 8601)")
    limit: int = Field(50, ge=1, le=500, description="Cantidad de registros")
    offset: int = Field(0, ge=0, description="Desplazamiento para paginacion")
