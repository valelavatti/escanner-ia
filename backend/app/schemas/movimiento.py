"""Pydantic schemas for stock movements (movimientos) and audit trail."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class MovimientoCreate(BaseModel):
    """Request body to create a stock movement.

    For ``alta``, ``cantidad`` is the amount to add. For ``ajuste``,
    ``cantidad`` is the new absolute stock.

    ``drain_bucket_qty`` (Slice 8 — Bug 2 fix + Feature): how many units
    of the entered ``cantidad`` should come FROM the product's
    ``stock_sin_ubicacion`` bucket ("rescuing" bucket units into the
    scanned ubicacion). 0 (default) means the alta/ajuste is a pure
    physical increment — no bucket drain, no ``rescate_sin_ubicacion``
    audit row. When > 0 the surgery inside
    ``_create_movimiento_once`` drains the bucket by EXACTLY
    ``drain_bucket_qty`` (validate it is <= the bucket's available qty
    AND <= ``cantidad``; cannot ingest more units into the ubicacion
    than the alta declares) and writes an additional
    ``rescate_sin_ubicacion`` audit row with conservation snapshots
    (anterior=nuevo on ``stock_general`` — bucket→physical is internal
    so the user-visible total is unchanged by the rescue; the bucket
    snapshots anterior=new would be WRONG — anterior=bucket_full,
    nuevo=bucket_full-drain_qty).
    """

    producto_sku: str = Field(..., min_length=1, description="SKU del producto")
    ubicacion_id: int = Field(..., ge=1, description="ID de la ubicacion")
    cantidad: int = Field(..., description="Cantidad para alta o stock absoluto para ajuste")
    tipo: Literal["alta", "ajuste"] = Field(default="alta", description="Tipo de movimiento")
    drain_bucket_qty: int = Field(
        default=0,
        ge=0,
        description=(
            "Slice 8 — unidades a drenar desde 'sin ubicación' para "
            "componer la cantidad ingresada. 0 = sin drenaje (alta pura). "
            "Debe ser <= cantidad y <= bucket disponible (si no, 400)."
        ),
    )


class MovimientoResponse(BaseModel):
    """Full movement record returned by the API."""

    id: int
    usuario_id: Optional[int] = None
    usuario_nombre: Optional[str] = None
    producto_sku: Optional[str] = None
    producto_descripcion: Optional[str] = None
    ubicacion_id: int
    ubicacion_qr: str
    estante_nombre: str
    fila: int
    columna: int
    fila_label: str
    columna_label: str
    cantidad: int
    stock_anterior: int
    stock_nuevo: int
    timestamp: datetime
    tipo: str
    stock_general_anterior: int = Field(default=0, description="Stock general del producto ANTES de este movimiento")
    stock_general_nuevo: int = Field(default=0, description="Stock general del producto DESPUES de este movimiento")
    stock_sin_ubicacion_anterior: int = Field(
        default=0,
        description=(
            "Slice 8 — unidades del producto en el bucket 'sin ubicación' "
            "ANTES de este movimiento. 0 para rows históricas (pre-017)."
        ),
    )
    stock_sin_ubicacion_nuevo: int = Field(
        default=0,
        description=(
            "Slice 8 — unidades del producto en el bucket 'sin ubicación' "
            "DESPUES de este movimiento. 0 para rows históricas (pre-017)."
        ),
    )


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
