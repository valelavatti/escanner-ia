"""Estante (shelf) administration endpoints."""

import asyncio
import zipfile
from io import BytesIO
from sqlite3 import IntegrityError
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.v1.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.repositories import estante_repository, ubicacion_repository
from app.schemas.auth import UsuarioResponse
from app.schemas.estante import (
    ConfirmDeleteOutOfBoundsRequest,
    DepositoResponse,
    EstanteCreate,
    EstanteDetailResponse,
    EstanteResponse,
    EstanteUpdate,
    EstanteUpdateResponse,
    UbicacionResponse,
)
from app.services import qr as qr_service

router = APIRouter()
depositos_router = APIRouter()


def _estante_response(row: dict) -> EstanteResponse:
    return EstanteResponse(
        id=row["id"],
        nombre=row["nombre"],
        orden_visual=row["orden_visual"],
        filas=row["filas"],
        columnas=row["columnas"],
        deposito_id=row.get("deposito_id"),
        deposito_nombre=row.get("deposito_nombre"),
        deleted_at=row.get("deleted_at"),
        created_at=row.get("created_at"),
        ubicaciones_count=row.get("ubicaciones_count", 0),
    )


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


@router.post("", response_model=EstanteResponse, status_code=status.HTTP_201_CREATED)
async def create_estante(
    data: EstanteCreate,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Create a new estante and auto-generate its ubicaciones grid."""
    existing = await estante_repository.get_estante_by_name(db, data.nombre)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un estante con el nombre '{data.nombre}'",
        )

    try:
        estante_id = await estante_repository.create_estante(
            db,
            data.nombre,
            data.orden_visual,
            data.filas,
            data.columnas,
            deposito_id=data.deposito_id,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un estante con el nombre '{data.nombre}'",
        )

    estante = await estante_repository.get_estante_by_id(db, estante_id)
    ubicaciones = await ubicacion_repository.list_ubicaciones_by_estante(db, estante_id)
    estante["ubicaciones_count"] = len(ubicaciones)
    return _estante_response(estante)


@router.get("", response_model=list[EstanteResponse])
async def list_estantes(
    include_deleted: bool = Query(False),
    deposito_id: Optional[int] = Query(None),
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """List all estantes ordered by visual order."""
    rows = await estante_repository.list_estantes(
        db, include_deleted=include_deleted, deposito_id=deposito_id
    )
    return [_estante_response(row) for row in rows]


@depositos_router.get("", response_model=list[DepositoResponse])
async def list_depositos(
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """List all depositos (warehouses) ordered by name."""
    rows = await estante_repository.list_depositos(db)
    return [DepositoResponse(id=row["id"], nombre=row["nombre"]) for row in rows]


@router.get("/{estante_id}", response_model=EstanteDetailResponse)
async def get_estante(
    estante_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Return a single estante with all its ubicaciones."""
    estante = await estante_repository.get_estante_by_id(db, estante_id)
    if estante is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estante no encontrado",
        )

    ubicaciones = await ubicacion_repository.list_ubicaciones_by_estante(db, estante_id)
    estante["ubicaciones_count"] = len(ubicaciones)

    return EstanteDetailResponse(
        **_estante_response(estante).model_dump(),
        ubicaciones=[_ubicacion_response(u) for u in ubicaciones],
    )


@router.put("/{estante_id}", response_model=EstanteUpdateResponse)
async def update_estante(
    estante_id: int,
    data: EstanteUpdate,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Update an estante's dimensions and/or visual order.

    Shrinking the grid flags out-of-bounds ubicaciones (returned in
    `out_of_bounds`) without deleting them. Expanding the grid generates new
    cells and clears any previously flagged cells that are now in bounds.
    """
    current = await estante_repository.get_estante_by_id(db, estante_id)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estante no encontrado",
        )

    old_filas = current["filas"]
    old_columnas = current["columnas"]

    if data.orden_visual is not None and data.orden_visual != current["orden_visual"]:
        current = await estante_repository.update_estante_orden(
            db, estante_id, data.orden_visual
        )
        if current is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Estante no encontrado",
            )

    new_filas = data.filas if data.filas is not None else old_filas
    new_columnas = data.columnas if data.columnas is not None else old_columnas

    out_of_bounds: list[dict] = []
    if (new_filas, new_columnas) != (old_filas, old_columnas):
        updated = await estante_repository.update_estante_dimensions(
            db, estante_id, new_filas, new_columnas
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Estante no encontrado",
            )
        current = updated

        if new_filas < old_filas or new_columnas < old_columnas:
            out_of_bounds = await ubicacion_repository.get_out_of_bounds_ubicaciones(
                db, estante_id, new_filas, new_columnas
            )

    ubicaciones = await ubicacion_repository.list_ubicaciones_by_estante(db, estante_id)
    current["ubicaciones_count"] = len(ubicaciones)

    return EstanteUpdateResponse(
        estante=_estante_response(current),
        out_of_bounds=[_ubicacion_response(u) for u in out_of_bounds],
    )


@router.delete("/{estante_id}")
async def delete_estante(
    estante_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Soft delete an estante, preserving its ubicaciones and audit history."""
    deleted = await estante_repository.soft_delete_estante(db, estante_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estante no encontrado",
        )
    return {"ok": True}


@router.post("/{estante_id}/confirm-delete-out-of-bounds")
async def confirm_delete_out_of_bounds(
    estante_id: int,
    data: ConfirmDeleteOutOfBoundsRequest,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Hard delete the listed out-of-bounds ubicaciones after user confirmation.

    Only ubicaciones that belong to this estante can be deleted.
    """
    ubicaciones = await ubicacion_repository.list_ubicaciones_by_estante(db, estante_id)
    valid_ids = {u["id"] for u in ubicaciones}
    ids_to_delete = [uid for uid in data.ubicacion_ids if uid in valid_ids]

    try:
        deleted = await ubicacion_repository.hard_delete_ubicaciones(db, ids_to_delete)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pueden eliminar ubicaciones con historial de movimientos",
        )

    return {"deleted": deleted}


@router.get("/{estante_id}/ubicaciones", response_model=list[UbicacionResponse])
async def list_ubicaciones_for_estante(
    estante_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """List all ubicaciones that belong to a given estante."""
    estante = await estante_repository.get_estante_by_id(db, estante_id)
    if estante is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estante no encontrado",
        )

    ubicaciones = await ubicacion_repository.list_ubicaciones_by_estante(db, estante_id)
    return [_ubicacion_response(u) for u in ubicaciones]


@router.get("/{estante_id}/qrs")
async def download_estante_qrs_zip(
    estante_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Download all QR codes for an estante as a ZIP archive."""
    estante = await estante_repository.get_estante_by_id(db, estante_id)
    if estante is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estante no encontrado",
        )

    qr_items = await qr_service.generate_estante_qrs(
        estante_id, db, get_settings().qr_default_size
    )

    def _build_zip() -> bytes:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for qr_valor, png_bytes in qr_items:
                filename = f"{qr_service._sanitize_qr_valor(qr_valor)}.png"
                archive.writestr(filename, png_bytes)
        return buffer.getvalue()

    zip_bytes = await asyncio.to_thread(_build_zip)
    filename = f"qr_{estante['nombre']}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{estante_id}/qrs/print")
async def print_estante_qrs(
    estante_id: int,
    per_page: int = Query(default=4),
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Return a printable multi-page A4 PDF with all QRs for an estante."""
    if per_page not in qr_service._VALID_PER_PAGE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"per_page debe ser uno de: {sorted(qr_service._VALID_PER_PAGE)}",
        )

    estante = await estante_repository.get_estante_by_id(db, estante_id)
    if estante is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estante no encontrado",
        )

    # Generate QRs at the resolution required to fill the A4 cell cleanly.
    qr_draw_size = qr_service._calculate_qr_display_size(per_page)[0]
    qr_resolution = max(qr_draw_size, qr_service._MIN_QR_RESOLUTION)
    qr_items = await qr_service.generate_estante_qrs(estante_id, db, qr_resolution)
    pdf_bytes = await qr_service.generate_pdf_print_sheet(qr_items, per_page)

    filename = f"qr_print_{estante['nombre']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
