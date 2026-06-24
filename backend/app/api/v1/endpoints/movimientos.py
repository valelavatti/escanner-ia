"""Movimientos (stock movement / audit trail) endpoints."""

from typing import Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.repositories import movimiento_repository
from app.schemas.auth import UsuarioResponse
from app.schemas.movimiento import (
    MovimientoCreate,
    MovimientoListResponse,
    MovimientoResponse,
)

router = APIRouter()


def _movimiento_response(row: dict) -> MovimientoResponse:
    return MovimientoResponse(
        id=row["id"],
        usuario_id=row["usuario_id"],
        usuario_nombre=row["usuario_nombre"],
        producto_sku=row.get("producto_sku"),
        producto_descripcion=row.get("producto_descripcion"),
        ubicacion_id=row["ubicacion_id"],
        ubicacion_qr=row["ubicacion_qr"],
        estante_nombre=row["estante_nombre"],
        fila=row["fila"],
        columna=row["columna"],
        cantidad=row["cantidad"],
        stock_anterior=row["stock_anterior"],
        stock_nuevo=row["stock_nuevo"],
        timestamp=row["timestamp"],
        tipo=row["tipo"],
        stock_general_anterior=row.get("stock_general_anterior", 0),
        stock_general_nuevo=row.get("stock_general_nuevo", 0),
    )


@router.post(
    "",
    response_model=MovimientoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_movimiento(
    data: MovimientoCreate,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Create a stock movement.

    The authenticated user is recorded as the author. The movement updates the
    location's stock (or sums into Suelto) atomically inside a SQLite
    transaction with SQLITE_BUSY retry.
    """
    try:
        row = await movimiento_repository.create_movimiento(
            db,
            usuario_id=user.id,
            producto_sku=data.producto_sku,
            ubicacion_id=data.ubicacion_id,
            cantidad=data.cantidad,
            tipo=data.tipo,
        )
    except movimiento_repository.ProductoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except movimiento_repository.UbicacionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except movimiento_repository.NegativeStockError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El stock no puede ser negativo",
        )
    except movimiento_repository.DatabaseBusyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos ocupada, intente nuevamente",
        )

    return _movimiento_response(row)


@router.get("", response_model=MovimientoListResponse)
async def list_movimientos(
    usuario_id: Optional[int] = Query(None),
    producto_sku: Optional[str] = Query(None),
    ubicacion_id: Optional[int] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """List movements with optional filters and pagination."""
    filters = {
        "usuario_id": usuario_id,
        "producto_sku": producto_sku,
        "ubicacion_id": ubicacion_id,
        "from_date": from_date,
        "to_date": to_date,
        "limit": limit,
        "offset": offset,
    }
    rows, total = await movimiento_repository.list_movimientos(db, filters)
    return MovimientoListResponse(
        items=[_movimiento_response(row) for row in rows],
        total=total,
    )


@router.get("/export", response_class=PlainTextResponse)
async def export_movimientos(
    usuario_id: Optional[int] = Query(None),
    producto_sku: Optional[str] = Query(None),
    ubicacion_id: Optional[int] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Export filtered movements as a UTF-8 CSV file."""
    filters = {
        "usuario_id": usuario_id,
        "producto_sku": producto_sku,
        "ubicacion_id": ubicacion_id,
        "from_date": from_date,
        "to_date": to_date,
    }
    csv_text = await movimiento_repository.export_movimientos_csv(db, filters)
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=movimientos.csv"},
    )


@router.get("/{movimiento_id}", response_model=MovimientoResponse)
async def get_movimiento(
    movimiento_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Get a single movement by ID."""
    row = await movimiento_repository.get_movimiento_by_id(db, movimiento_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movimiento no encontrado",
        )
    return _movimiento_response(row)
