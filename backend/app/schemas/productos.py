"""Pydantic schemas for product endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UbicacionStockInfo(BaseModel):
    """Stock information for a product at a specific location."""

    ubicacion_id: int
    stock_actual: int
    is_assigned: bool


class ProductOut(BaseModel):
    sku: str
    descripcion: str
    codigo_de_barra: str
    created_at: Optional[datetime] = None
    ubicacion_stock: Optional[UbicacionStockInfo] = Field(
        default=None,
        description="Stock info for the requested ubicacion_id, if provided",
    )


class ProductSearchResponse(BaseModel):
    items: list[ProductOut]
    total: int
