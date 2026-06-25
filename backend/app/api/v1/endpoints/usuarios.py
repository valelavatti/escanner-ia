"""Admin-only user management endpoints."""

from sqlite3 import IntegrityError
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import get_current_user, require_admin
from app.core.database import get_db
from app.repositories import auth_repository, usuario_repository
from app.schemas.auth import UsuarioResponse
from app.schemas.usuario import (
    DepositoAssignRequest,
    DepositoAssignment,
    UsuarioCreate,
    UsuarioUpdate,
    UsuarioWithDepositos,
)

router = APIRouter()


def _usuario_with_depositos(user: dict) -> UsuarioWithDepositos:
    return UsuarioWithDepositos(
        id=user["id"],
        nombre=user["nombre"],
        is_admin=user["is_admin"],
        depositos=[
            DepositoAssignment(
                deposito_id=d["deposito_id"],
                deposito_nombre=d["deposito_nombre"],
                role=d["role"],
            )
            for d in user.get("depositos", [])
        ],
    )


@router.get("", response_model=list[UsuarioWithDepositos])
async def list_usuarios(
    db: aiosqlite.Connection = Depends(get_db),
    admin: UsuarioResponse = Depends(require_admin),
):
    """List all users with their depósito assignments. Requires admin."""
    users = await usuario_repository.list_usuarios_with_depositos(db)
    return [_usuario_with_depositos(u) for u in users]


@router.post("", response_model=UsuarioWithDepositos, status_code=status.HTTP_201_CREATED)
async def create_usuario(
    data: UsuarioCreate,
    db: aiosqlite.Connection = Depends(get_db),
    admin: UsuarioResponse = Depends(require_admin),
):
    """Create a new user with a hashed password. Requires admin."""
    existing = await usuario_repository.get_usuario_by_name(db, data.nombre)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un usuario con el nombre '{data.nombre}'",
        )

    password_hash = auth_repository.hash_password(data.password)
    user_id = await usuario_repository.create_usuario(
        db, data.nombre, password_hash, data.is_admin
    )

    user = await usuario_repository.get_usuario_by_id(db, user_id)
    user["depositos"] = []
    return _usuario_with_depositos(user)


@router.put("/{usuario_id}", response_model=UsuarioWithDepositos)
async def update_usuario(
    usuario_id: int,
    data: UsuarioUpdate,
    db: aiosqlite.Connection = Depends(get_db),
    admin: UsuarioResponse = Depends(require_admin),
):
    """Update a user's name, password, and/or admin flag. Requires admin."""
    user = await usuario_repository.get_usuario_by_id(db, usuario_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    if data.nombre is not None:
        existing = await usuario_repository.get_usuario_by_name(db, data.nombre)
        if existing is not None and existing["id"] != usuario_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un usuario con el nombre '{data.nombre}'",
            )

    password_hash: Optional[str] = None
    if data.password is not None:
        password_hash = auth_repository.hash_password(data.password)

    updated = await usuario_repository.update_usuario(
        db,
        usuario_id,
        nombre=data.nombre,
        password_hash=password_hash,
        is_admin=data.is_admin,
    )

    updated["depositos"] = await usuario_repository.get_user_depositos(db, usuario_id)
    return _usuario_with_depositos(updated)


@router.delete("/{usuario_id}")
async def delete_usuario(
    usuario_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    admin: UsuarioResponse = Depends(require_admin),
):
    """Delete a user. Requires admin. Rejects self-delete and last-admin delete."""
    if usuario_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puede eliminarse a sí mismo",
        )

    user = await usuario_repository.get_usuario_by_id(db, usuario_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    if user["is_admin"] and await usuario_repository.count_admins(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe existir al menos un administrador",
        )

    await usuario_repository.delete_usuario(db, usuario_id)
    return {"ok": True}


@router.get("/{usuario_id}/depositos", response_model=list[DepositoAssignment])
async def list_usuario_depositos(
    usuario_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    admin: UsuarioResponse = Depends(require_admin),
):
    """List depósito assignments for a user. Requires admin."""
    user = await usuario_repository.get_usuario_by_id(db, usuario_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    depositos = await usuario_repository.get_user_depositos(db, usuario_id)
    return [
        DepositoAssignment(
            deposito_id=d["deposito_id"],
            deposito_nombre=d["deposito_nombre"],
            role=d["role"],
        )
        for d in depositos
    ]


@router.post(
    "/{usuario_id}/depositos",
    response_model=DepositoAssignment,
    status_code=status.HTTP_201_CREATED,
)
async def assign_usuario_deposito(
    usuario_id: int,
    data: DepositoAssignRequest,
    db: aiosqlite.Connection = Depends(get_db),
    admin: UsuarioResponse = Depends(require_admin),
):
    """Assign a depósito role to a user. Requires admin."""
    user = await usuario_repository.get_usuario_by_id(db, usuario_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    try:
        await usuario_repository.assign_deposito(
            db, usuario_id, data.deposito_id, data.role
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya tiene asignado ese depósito",
        )

    deposito = await usuario_repository.get_user_depositos(db, usuario_id)
    for d in deposito:
        if d["deposito_id"] == data.deposito_id:
            return DepositoAssignment(
                deposito_id=d["deposito_id"],
                deposito_nombre=d["deposito_nombre"],
                role=d["role"],
            )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo confirmar la asignación",
    )


@router.delete("/{usuario_id}/depositos/{deposito_id}")
async def remove_usuario_deposito(
    usuario_id: int,
    deposito_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    admin: UsuarioResponse = Depends(require_admin),
):
    """Remove a depósito assignment from a user. Requires admin."""
    user = await usuario_repository.get_usuario_by_id(db, usuario_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    removed = await usuario_repository.unassign_deposito(db, usuario_id, deposito_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asignación no encontrada",
        )
    return {"ok": True}
