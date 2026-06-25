"""Auth endpoints: login, logout, current session."""

from datetime import datetime, timedelta, timezone

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.repositories import auth_repository, usuario_repository
from app.schemas.auth import (
    DepositoAssignment,
    LoginRequest,
    LoginResponse,
    MeResponse,
    UsuarioResponse,
)

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
    """Create a session for a user after verifying their password."""
    user = await auth_repository.get_user_by_name(db, data.nombre)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    if user.get("password_hash") is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario sin contraseña configurada. Contacte al administrador.",
        )

    if not auth_repository.verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    token = await auth_repository.create_session(db, user["id"])
    await auth_repository.update_last_login(db, user["id"])

    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=auth_repository.SESSION_TTL_HOURS
    )
    return LoginResponse(
        token=token,
        usuario=UsuarioResponse(
            id=user["id"], nombre=user["nombre"], is_admin=bool(user["is_admin"])
        ),
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
    user: UsuarioResponse = Depends(get_current_user),
):
    """Return the currently authenticated user and their depósito assignments."""
    depositos = await usuario_repository.get_user_depositos(db, user.id)
    return MeResponse(
        usuario=user,
        depositos=[
            DepositoAssignment(
                deposito_id=d["deposito_id"],
                deposito_nombre=d["deposito_nombre"],
                role=d["role"],
            )
            for d in depositos
        ],
    )
