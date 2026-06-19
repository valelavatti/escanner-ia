"""Product lookup endpoints."""

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.repositories import producto_repository
from app.schemas.auth import UsuarioResponse
from app.schemas.productos import ProductOut, ProductSearchResponse

router = APIRouter()


def _product_out(row: dict) -> ProductOut:
    return ProductOut(
        sku=row["sku"],
        descripcion=row["descripcion"],
        codigo_de_barra=row["codigo_de_barra"],
        created_at=row.get("created_at"),
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


@router.get("/{codigo_de_barra}", response_model=ProductOut)
async def get_producto_by_barcode(
    codigo_de_barra: str,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Look up a single product by exact barcode."""
    row = await producto_repository.get_producto_by_codigo(db, codigo_de_barra)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )
    return _product_out(row)
