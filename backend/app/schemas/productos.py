"""Pydantic schemas for product endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UbicacionStockInfo(BaseModel):
    """Stock information for a product at a specific location."""

    ubicacion_id: int
    stock_actual: int
    is_assigned: bool
    existing_producto_sku: Optional[str] = Field(
        default=None,
        description="If the location already has a different product, its SKU",
    )
    existing_producto_stock: Optional[int] = Field(
        default=None,
        description="Live stock of the existing product that would be lost on reassignment",
    )


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


class ProductoUbicacionItem(BaseModel):
    """One ubicacion where a product has stock."""

    ubicacion_id: int
    estante_nombre: str
    qr_valor: str
    fila: int
    columna: int
    fila_label: str
    columna_label: str
    stock: int
    deposito_nombre: str


class ProductoUbicacionesResponse(BaseModel):
    """All ubicaciones where a product has stock, plus the permission-filtered total."""

    sku: str
    descripcion: str
    codigo_de_barra: str
    stock_total: int
    ubicaciones: list[ProductoUbicacionItem]
