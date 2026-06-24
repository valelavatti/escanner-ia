"""Product lookup endpoints."""

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.repositories import movimiento_repository, producto_repository
from app.schemas.auth import UsuarioResponse
from app.schemas.productos import ProductOut, ProductSearchResponse, UbicacionStockInfo

router = APIRouter()


def _product_out(row: dict, ubicacion_stock: dict | None = None) -> ProductOut:
    stock_info = None
    if ubicacion_stock is not None:
        stock_info = UbicacionStockInfo(
            ubicacion_id=ubicacion_stock["ubicacion_id"],
            stock_actual=ubicacion_stock["stock_actual"],
            is_assigned=ubicacion_stock["is_assigned"],
            existing_producto_sku=ubicacion_stock.get("existing_producto_sku"),
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


@router.get("/{codigo_de_barra}/stock-total", response_model=dict)
async def get_producto_stock_total(
    codigo_de_barra: str,
    sku: str = Query(None, description="SKU del producto (si ya se conoce)"),
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Return the total stock of a product across all ubicaciones."""
    if sku:
        total = await movimiento_repository.get_producto_stock_total(db, sku)
        return {"sku": sku, "stock_total": total}

    row = await producto_repository.get_producto_by_codigo(db, codigo_de_barra)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )
    total = await movimiento_repository.get_producto_stock_total(db, row["sku"])
    return {"sku": row["sku"], "stock_total": total}


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
