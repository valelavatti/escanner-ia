"""Usuario repository for listing and fetching seeded users."""

from typing import Optional

import aiosqlite


async def list_usuarios(db: aiosqlite.Connection) -> list[dict]:
    """Return all users ordered by name."""
    async with db.execute(
        "SELECT id, nombre, created_at, last_login_at FROM usuarios ORDER BY nombre"
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_usuario_by_id(db: aiosqlite.Connection, usuario_id: int) -> Optional[dict]:
    """Return a single user by ID, or None if not found."""
    async with db.execute(
        "SELECT id, nombre, created_at, last_login_at FROM usuarios WHERE id = ?",
        (usuario_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)
