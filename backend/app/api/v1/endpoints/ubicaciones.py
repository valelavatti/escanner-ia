"""Ubicacion (shelf cell) endpoints."""

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.v1.deps import (
    get_current_user,
    require_deposito_access,
    require_deposito_role,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.repositories import ubicacion_repository
from app.schemas.auth import UsuarioResponse
from app.schemas.estante import UbicacionAssignRequest, UbicacionResponse
from app.services import qr as qr_service

router = APIRouter()


def _ubicacion_response(row: dict) -> UbicacionResponse:
    return UbicacionResponse(
        id=row["id"],
        estante_id=row["estante_id"],
        estante_nombre=row["estante_nombre"],
        fila=row["fila"],
        columna=row["columna"],
        producto_id=row.get("producto_id"),
        producto_sku=row.get("producto_sku") or row.get("producto_id"),
        producto_descripcion=row.get("producto_descripcion"),
        stock_actual=row["stock_actual"],
        qr_valor=row["qr_valor"],
        estado=row["estado"],
    )


@router.put("/{ubicacion_id}/assign", response_model=UbicacionResponse)
async def assign_producto_to_ubicacion(
    ubicacion_id: int,
    data: UbicacionAssignRequest,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Assign a product SKU to an empty ubicacion.

    The "Suelto" shelf is a catch-all for loose products and does NOT support
    1:1 product assignment. Its stock comes from movimientos, not from
    ubicaciones.producto_id.
    """
    ubicacion = await ubicacion_repository.get_ubicacion_by_id(db, ubicacion_id)
    if ubicacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ubicacion no encontrada",
        )

    await require_deposito_role(
        user,
        ubicacion.get("deposito_id"),
        db,
        allowed_roles={"admin", "operator"},
    )

    # Block assignment to the Suelto catch-all shelf.
    if ubicacion.get("estante_nombre") == "Suelto":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El estante Suelto no admite asignacion de productos individuales. "
            "Los productos sueltos se cargan via escaneo sin QR de sector.",
        )

    try:
        await ubicacion_repository.assign_producto_to_ubicacion(
            db, ubicacion_id, data.producto_id, user.id
        )
    except ubicacion_repository.UbicacionOcupadaError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La ubicacion ya tiene un producto asignado",
        )

    updated = await ubicacion_repository.get_ubicacion_by_id(db, ubicacion_id)
    return _ubicacion_response(updated)


@router.delete("/{ubicacion_id}/assign", response_model=UbicacionResponse)
async def unassign_producto_from_ubicacion(
    ubicacion_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Remove the product assignment from a ubicacion.

    Sets producto_id = NULL. The ubicacion becomes available for a new product.
    Historical movimientos are preserved (append-only audit trail).
    """
    ubicacion = await ubicacion_repository.get_ubicacion_by_id(db, ubicacion_id)
    if ubicacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ubicacion no encontrada",
        )

    await require_deposito_role(
        user,
        ubicacion.get("deposito_id"),
        db,
        allowed_roles={"admin", "operator"},
    )

    if ubicacion.get("producto_id") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La ubicacion no tiene un producto asignado",
        )

    await ubicacion_repository.unassign_producto_from_ubicacion(db, ubicacion_id, user.id)
    updated = await ubicacion_repository.get_ubicacion_by_id(db, ubicacion_id)
    return _ubicacion_response(updated)


@router.get("/{ubicacion_id}/qr.png")
async def get_ubicacion_qr_png(
    ubicacion_id: int,
    size: int = Query(default_factory=lambda: get_settings().qr_default_size, ge=50, le=2000),
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Return the QR PNG for a single ubicacion."""
    ubicacion = await ubicacion_repository.get_ubicacion_by_id(db, ubicacion_id)
    if ubicacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ubicacion no encontrada",
        )

    await require_deposito_access(user, ubicacion.get("deposito_id"), db)

    png_bytes = await qr_service.get_or_create_qr_bytes(ubicacion["qr_valor"], size)
    return Response(content=png_bytes, media_type="image/png")
