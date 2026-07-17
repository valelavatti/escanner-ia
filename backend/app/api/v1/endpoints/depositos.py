"""Deposito (warehouse) management endpoints.

``GET /depositos`` is open to any authenticated user; non-admins only see the
depositos assigned to them. All write operations (POST/PUT/DELETE) require a
global admin via ``require_admin``.
"""

from sqlite3 import IntegrityError

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import get_current_user, get_deposito_ids_for_user, require_admin
from app.core.database import get_db
from app.repositories import deposito_repository
from app.schemas.auth import UsuarioResponse
from app.schemas.deposito import (
    DepositoCreate,
    DepositoUpdate,
    DepositoWithStats,
)

router = APIRouter()


def _deposito_with_stats(row: dict) -> DepositoWithStats:
    return DepositoWithStats(
        id=row["id"],
        nombre=row["nombre"],
        created_at=row.get("created_at"),
        estantes_count=row.get("estantes_count", 0),
        usuarios_count=row.get("usuarios_count", 0),
    )


@router.get("", response_model=list[DepositoWithStats])
async def list_depositos(
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """List depositos with estantes/usuarios counts, ordered by name.

    Non-admins only see depositos assigned to them.
    """
    deposito_ids = await get_deposito_ids_for_user(db, user)
    rows = await deposito_repository.list_depositos_with_stats(db, deposito_ids)
    return [_deposito_with_stats(row) for row in rows]


@router.post(
    "",
    response_model=DepositoWithStats,
    status_code=status.HTTP_201_CREATED,
)
async def create_deposito(
    data: DepositoCreate,
    db: aiosqlite.Connection = Depends(get_db),
    admin: UsuarioResponse = Depends(require_admin),
):
    """Create a new deposito. Requires admin.

    Returns 409 when a deposito with the same name already exists.
    """
    existing = await deposito_repository.get_deposito_by_name(db, data.nombre)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un depósito con el nombre '{data.nombre}'",
        )

    try:
        deposito_id = await deposito_repository.create_deposito(db, data.nombre)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un depósito con el nombre '{data.nombre}'",
        )

    rows = await deposito_repository.list_depositos_with_stats(db, [deposito_id])
    return _deposito_with_stats(rows[0])


@router.put("/{deposito_id}", response_model=DepositoWithStats)
async def update_deposito(
    deposito_id: int,
    data: DepositoUpdate,
    db: aiosqlite.Connection = Depends(get_db),
    admin: UsuarioResponse = Depends(require_admin),
):
    """Update a deposito's name. Requires admin.

    Returns 404 when the deposito does not exist and 409 when the new name is
    already taken by another deposito.
    """
    deposito = await deposito_repository.get_deposito_by_id(db, deposito_id)
    if deposito is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Depósito no encontrado",
        )

    if data.nombre != deposito["nombre"]:
        existing = await deposito_repository.get_deposito_by_name(db, data.nombre)
        if existing is not None and existing["id"] != deposito_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un depósito con el nombre '{data.nombre}'",
            )

    try:
        updated = await deposito_repository.update_deposito(
            db, deposito_id, data.nombre
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un depósito con el nombre '{data.nombre}'",
        )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Depósito no encontrado",
        )

    rows = await deposito_repository.list_depositos_with_stats(db, [deposito_id])
    return _deposito_with_stats(rows[0])


@router.delete("/{deposito_id}")
async def delete_deposito(
    deposito_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    admin: UsuarioResponse = Depends(require_admin),
):
    """Delete a deposito. Requires admin.

    Rejects deletion with 400 when the deposito has estantes assigned (the
    ``estantes.deposito_id`` FK has no ON DELETE clause, so SQLite would
    reject it anyway) or when it is the last remaining deposito.
    ``usuario_deposito`` assignments are removed by ON DELETE CASCADE.
    """
    deposito = await deposito_repository.get_deposito_by_id(db, deposito_id)
    if deposito is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Depósito no encontrado",
        )

    estantes_count = await deposito_repository.count_estantes_for_deposito(
        db, deposito_id
    )
    if estantes_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar un depósito con estantes asignados",
        )

    if await deposito_repository.count_depositos(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe existir al menos un depósito",
        )

    await deposito_repository.delete_deposito(db, deposito_id)
    return {"ok": True}
