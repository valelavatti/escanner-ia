"""Public user list endpoint used by the login screen."""

import aiosqlite
from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.repositories import usuario_repository
from app.schemas.auth import UsuarioResponse

router = APIRouter()


@router.get("", response_model=list[UsuarioResponse])
async def list_usuarios(db: aiosqlite.Connection = Depends(get_db)):
    """Return all seeded users for the login name-selection screen."""
    rows = await usuario_repository.list_usuarios(db)
    return [UsuarioResponse(id=row["id"], nombre=row["nombre"]) for row in rows]
