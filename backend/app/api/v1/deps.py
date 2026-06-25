"""Shared FastAPI dependencies, including the session auth guard and permission helpers."""

from dataclasses import dataclass
from typing import Optional

import aiosqlite
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import get_db
from app.repositories import auth_repository, usuario_repository
from app.schemas.auth import UsuarioResponse

_security = HTTPBearer(auto_error=False)


async def get_current_user(
    db: aiosqlite.Connection = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> UsuarioResponse:
    """Validate the Bearer token and return the authenticated user.

    Use this dependency on every protected endpoint.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session = await auth_repository.get_session(db, credentials.credentials)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion invalida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UsuarioResponse(
        id=session["usuario_id"],
        nombre=session["nombre"],
        is_admin=bool(session["is_admin"]),
    )


def require_admin(user: UsuarioResponse = Depends(get_current_user)) -> UsuarioResponse:
    """Dependency that raises 403 if the authenticated user is not a global admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requiere permisos de administrador",
        )
    return user


async def get_deposito_ids_for_user(
    db: aiosqlite.Connection,
    user: UsuarioResponse,
) -> Optional[list[int]]:
    """Return the list of depósito IDs accessible to the user.

    Returns None for global admins (no filtering). For non-admins returns the
    user's assigned depósito IDs, which may be an empty list.
    """
    if user.is_admin:
        return None
    return await usuario_repository.get_deposito_ids_for_user(db, user.id)


async def require_deposito_access(
    user: UsuarioResponse,
    deposito_id: Optional[int],
    db: aiosqlite.Connection,
) -> None:
    """Raise 403 if the user cannot access the given depósito.

    Admins bypass the check. NULL depósito_id is denied to non-admins.
    """
    if user.is_admin:
        return
    if deposito_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a este depósito",
        )
    accessible = await get_deposito_ids_for_user(db, user)
    if accessible is None:
        return
    if deposito_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a este depósito",
        )


async def require_deposito_role(
    user: UsuarioResponse,
    deposito_id: Optional[int],
    db: aiosqlite.Connection,
    allowed_roles: set[str],
) -> None:
    """Raise 403 if the user lacks an allowed role for the given depósito.

    Admins bypass the role check but still require a non-NULL depósito_id.
    """
    if deposito_id is None and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a este depósito",
        )
    if user.is_admin:
        return
    role = await usuario_repository.get_user_role_for_deposito(db, user.id, deposito_id)
    if role is None or role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permiso para realizar esta operación en el depósito",
        )
