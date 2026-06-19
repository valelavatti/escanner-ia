"""Auth endpoints: login, logout, current session."""

from datetime import datetime, timedelta, timezone

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import get_db
from app.repositories import auth_repository
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse, UsuarioResponse

router = APIRouter()
_security = HTTPBearer(auto_error=False)


async def _require_token(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: aiosqlite.Connection = Depends(get_db)):
    """Create a session for a pre-seeded user selected by name."""
    user = await auth_repository.get_user_by_name(db, data.nombre)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    token = await auth_repository.create_session(db, user["id"])
    await auth_repository.update_last_login(db, user["id"])

    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=auth_repository.SESSION_TTL_HOURS
    )
    return LoginResponse(
        token=token,
        usuario=UsuarioResponse(id=user["id"], nombre=user["nombre"]),
        expires_at=expires_at,
    )


@router.post("/logout")
async def logout(
    db: aiosqlite.Connection = Depends(get_db),
    token: str = Depends(_require_token),
):
    """Invalidate the current session."""
    await auth_repository.delete_session(db, token)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
async def me(
    db: aiosqlite.Connection = Depends(get_db),
    token: str = Depends(_require_token),
):
    """Return the currently authenticated user."""
    session = await auth_repository.get_session(db, token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion invalida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return MeResponse(
        usuario=UsuarioResponse(id=session["usuario_id"], nombre=session["nombre"])
    )
