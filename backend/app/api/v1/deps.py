"""Shared FastAPI dependencies, including the session auth guard."""

import aiosqlite
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import get_db
from app.repositories import auth_repository
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

    return UsuarioResponse(id=session["usuario_id"], nombre=session["nombre"])
