"""Product lookup endpoints."""

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.deps import get_current_user, get_deposito_ids_for_user, require_admin
from app.core.database import get_db
from app.repositories import (
    movimiento_repository,
    producto_repository,
    stock_sin_ubicacion_repository,
    ubicacion_repository,
)
from app.schemas.auth import UsuarioResponse
from app.schemas.productos import (
    ProductOut,
    ProductSearchResponse,
    ProductoStockTotal,
    ProductoUbicacionesResponse,
    ProductoUbicacionItem,
    StockSinUbicacionListItem,
    UbicacionStockInfo,
)

router = APIRouter()


def _product_out(row: dict, ubicacion_stock: dict | None = None) -> ProductOut:
    stock_info = None
    if ubicacion_stock is not None:
        stock_info = UbicacionStockInfo(
            ubicacion_id=ubicacion_stock["ubicacion_id"],
            stock_actual=ubicacion_stock["stock_actual"],
            is_assigned=ubicacion_stock["is_assigned"],
            existing_producto_sku=ubicacion_stock.get("existing_producto_sku"),
            existing_producto_stock=ubicacion_stock.get("existing_producto_stock"),
        )
    return ProductOut(
        sku=row["sku"],
        descripcion=row["descripcion"],
        codigo_de_barra=row["codigo_de_barra"],
        created_at=row.get("created_at"),
        ubicacion_stock=stock_info,
    )


@router.get("", response_model=ProductSearchResponse)
async def list_productos(
    search: str = Query(..., min_length=1, description="Partial match on SKU, description or barcode"),
    limit: int = Query(20, ge=1, le=100),
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Search products by SKU, description, or barcode."""
    rows = await producto_repository.search_productos(db, search, limit=limit)
    items = [_product_out(row) for row in rows]
    return ProductSearchResponse(items=items, total=len(items))


@router.get("/sin-ubicacion", response_model=list[StockSinUbicacionListItem])
async def list_stock_sin_ubicacion(
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(require_admin),
):
    """List every product with units in the sin-ubicacion bucket (admin only).

    Returns one row per non-empty bucket entry, joining ``stock_sin_ubicacion``
    with ``productos`` on SKU. Each row pairs the bucket qty (``cantidad``)
    with the product SKU + description so admins can see what units are
    floating without a physical home (Slice 6 / Frontend Point 5).

    The bucket stays GLOBAL per product (no ``deposito_id``); per-deposito
    split is deferred to future multi-deposito work (user decision in this
    slice). Read-only — admin actions on the bucket are out of scope.

    Registered BEFORE ``/{codigo_de_barra}`` routes so FastAPI's path matcher
    resolves the literal segment ``sin-ubicacion`` here instead of binding it
    as a ``codigo_de_barra`` value (which would 404 on product lookup).
    """
    rows = await stock_sin_ubicacion_repository.list_all_with_producto(db)
    return [
        StockSinUbicacionListItem(
            producto_sku=row["producto_sku"],
            producto_descripcion=row["producto_descripcion"],
            cantidad=row["cantidad"],
            updated_at=row.get("updated_at"),
        )
        for row in rows
    ]


@router.get("/{codigo_de_barra}/stock-total", response_model=ProductoStockTotal)
async def get_producto_stock_total(
    codigo_de_barra: str,
    sku: str = Query(None, description="SKU del producto (si ya se conoce)"),
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Return the total stock of a product broken down into physical + bucket.

    Per spec REQ-X-002 + REQ-B-009, the displayed ``stock_total`` (the
    "stock general" the user sees) is the sum of physical ubicaciones stock
    (incl. Suelto movimiento sums) PLUS the ``stock_sin_ubicacion`` bucket
    qty for the product. The ``stock_sin_ubicacion`` field surfaces the
    bucket qty separately so the frontend can render the 3-stock breakdown
    without a second round-trip (Slice 6 / Frontend Point 4).

    ``movimiento_repository.get_producto_stock_total`` returns physical +
    Suelto only (the bucket is a separate flow); this endpoint ADDS the
    bucket qty here so the ``stock_total`` invariant (REQ-B-009) holds at
    the API boundary.
    """
    if sku:
        physical = await movimiento_repository.get_producto_stock_total(db, sku)
        bucket = await stock_sin_ubicacion_repository.get_cantidad(db, sku)
        return ProductoStockTotal(
            sku=sku,
            stock_total=physical + bucket,
            stock_sin_ubicacion=bucket,
        )

    row = await producto_repository.get_producto_by_codigo(db, codigo_de_barra)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )
    physical = await movimiento_repository.get_producto_stock_total(db, row["sku"])
    bucket = await stock_sin_ubicacion_repository.get_cantidad(db, row["sku"])
    return ProductoStockTotal(
        sku=row["sku"],
        stock_total=physical + bucket,
        stock_sin_ubicacion=bucket,
    )


@router.get("/{codigo_de_barra}/ubicaciones", response_model=ProductoUbicacionesResponse)
async def get_producto_ubicaciones(
    codigo_de_barra: str,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Return every ubicacion where the product has stock, filtered by deposito permissions.

    Regular shelves report ``stock`` from ``ubicaciones.stock_actual``; Suelto
    reports the SUM of ``movimientos.cantidad``. ``stock_total`` is the sum of
    the returned per-ubicacion stocks (matches the permission-filtered view).
    """
    row = await producto_repository.get_producto_by_codigo(db, codigo_de_barra)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )

    deposito_ids = await get_deposito_ids_for_user(db, user)
    ubicaciones = await movimiento_repository.get_producto_ubicaciones(
        db, row["sku"], deposito_ids
    )

    stock_total = sum(int(u["stock"]) for u in ubicaciones)
    items = []
    for u in ubicaciones:
        fila_label, columna_label = ubicacion_repository.compute_labels(u)
        items.append(
            ProductoUbicacionItem(
                ubicacion_id=u["ubicacion_id"],
                estante_nombre=u["estante_nombre"],
                qr_valor=u["qr_valor"],
                fila=u["fila"],
                columna=u["columna"],
                fila_label=fila_label,
                columna_label=columna_label,
                stock=int(u["stock"]),
                deposito_nombre=u["deposito_nombre"],
            )
        )
    return ProductoUbicacionesResponse(
        sku=row["sku"],
        descripcion=row["descripcion"],
        codigo_de_barra=row["codigo_de_barra"],
        stock_total=stock_total,
        ubicaciones=items,
    )


@router.get("/{codigo_de_barra}", response_model=ProductOut)
async def get_producto_by_barcode(
    codigo_de_barra: str,
    ubicacion_id: int | None = Query(None, ge=1, description="ID de ubicacion para incluir stock actual"),
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Look up a single product by exact barcode.

    If ``ubicacion_id`` is provided, the response includes the product's
    current stock and assignment state for that location.
    """
    row = await producto_repository.get_producto_by_codigo(db, codigo_de_barra)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )

    ubicacion_stock = None
    if ubicacion_id is not None:
        try:
            ubicacion_stock = await movimiento_repository.get_producto_ubicacion_stock(
                db, row["sku"], ubicacion_id
            )
            ubicacion_stock["ubicacion_id"] = ubicacion_id
        except movimiento_repository.UbicacionNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ubicacion no encontrada",
            )

    return _product_out(row, ubicacion_stock)
