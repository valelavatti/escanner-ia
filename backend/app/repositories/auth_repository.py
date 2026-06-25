"""Session and user lookup repository with bcrypt password hashing."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite
import bcrypt

SESSION_TTL_HOURS = 8


async def get_user_by_name(db: aiosqlite.Connection, nombre: str) -> Optional[dict]:
    """Look up a user by exact name. Returns a dict or None."""
    async with db.execute(
        "SELECT id, nombre, password_hash, is_admin, created_at, last_login_at FROM usuarios WHERE nombre = ?",
        (nombre,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def create_session(db: aiosqlite.Connection, usuario_id: int) -> str:
    """Create a new server-side session for the given user and return its token."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    await db.execute(
        "INSERT INTO sessions (id, token, usuario_id, expires_at) VALUES (?, ?, ?, ?)",
        (token, token, usuario_id, expires_at.isoformat()),
    )
    await db.commit()
    return token


async def get_session(db: aiosqlite.Connection, token: str) -> Optional[dict]:
    """Return active session info joined with the user, or None if invalid/expired."""
    now = datetime.now(timezone.utc).isoformat()
    async with db.execute(
        """
        SELECT s.id AS session_id,
               s.token,
               s.expires_at,
               u.id AS usuario_id,
               u.nombre,
               u.is_admin
        FROM sessions s
        JOIN usuarios u ON u.id = s.usuario_id
        WHERE s.token = ? AND s.expires_at > ?
        """,
        (token, now),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def delete_session(db: aiosqlite.Connection, token: str) -> bool:
    """Invalidate a session by token. Returns True if a row was deleted."""
    cursor = await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
    await db.commit()
    return cursor.rowcount > 0


async def update_last_login(db: aiosqlite.Connection, usuario_id: int) -> None:
    """Update the user's last login timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE usuarios SET last_login_at = ? WHERE id = ?",
        (now, usuario_id),
    )
    await db.commit()


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt and return the decoded ASCII hash."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    if not password_hash:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
