"""Sector QR lookup endpoint used by the scanner to anchor a location."""

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.deps import get_current_user, require_deposito_access
from app.core.database import get_db
from app.repositories import ubicacion_repository
from app.schemas.auth import UsuarioResponse
from app.schemas.estante import UbicacionResponse

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


@router.get("/lookup", response_model=UbicacionResponse)
async def lookup_sector(
    qr_valor: str = Query(..., min_length=1),
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Look up an active ubicacion by its QR value.

    This is what the scanner calls when a sector QR code is scanned.
    """
    ubicacion = await ubicacion_repository.get_ubicacion_by_qr(db, qr_valor)
    if ubicacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sector no encontrado",
        )

    await require_deposito_access(user, ubicacion.get("deposito_id"), db)
    return _ubicacion_response(ubicacion)
