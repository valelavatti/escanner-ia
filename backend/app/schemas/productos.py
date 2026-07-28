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
    """One ubicacion where a product has stock.

    ``ubicacion_id`` and ``qr_valor`` are Optional to support the synthetic
    sin-ubicacion bucket row (REQ-C-001, REQ-C-002, REQ-C-003): a product
    whose freed units live in the ``stock_sin_ubicacion`` bucket surfaces
    as a row with ``ubicacion_id = None``, ``qr_valor = None`` and
    ``estante_nombre = "SIN UBICACION"`` alongside its physical ubicaciones.
    The frontend renders the bucket row via the
    ``item.ubicacion_id === null`` discriminator (REQ-C-004..006). Physical
    ubicaciones (including Suelto, a real ``ubicaciones`` row with id=1)
    always carry non-null ``ubicacion_id`` and ``qr_valor`` (REQ-C-007, R5).
    """

    ubicacion_id: Optional[int] = None
    estante_nombre: str
    qr_valor: Optional[str] = None
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
