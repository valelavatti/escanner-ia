"""Usuario repository for admin user management and depósito assignments."""

from typing import Optional

import aiosqlite


async def list_usuarios_with_depositos(db: aiosqlite.Connection) -> list[dict]:
    """Return all users with their depósito assignments. Never exposes password_hash."""
    async with db.execute(
        """
        SELECT u.id, u.nombre, u.is_admin
        FROM usuarios u
        ORDER BY u.nombre
        """
    ) as cursor:
        users = [dict(row) for row in await cursor.fetchall()]

    for user in users:
        user["depositos"] = await get_user_depositos(db, user["id"])

    return users


async def list_usuarios(db: aiosqlite.Connection) -> list[dict]:
    """Return all users ordered by name (legacy public-list shape, no password_hash)."""
    async with db.execute(
        """
        SELECT id, nombre, is_admin, created_at, last_login_at
        FROM usuarios
        ORDER BY nombre
        """
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_usuario_by_id(db: aiosqlite.Connection, usuario_id: int) -> Optional[dict]:
    """Return a single user by ID without password_hash, or None if not found."""
    async with db.execute(
        """
        SELECT id, nombre, is_admin, created_at, last_login_at
        FROM usuarios WHERE id = ?
        """,
        (usuario_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def get_usuario_by_name(
    db: aiosqlite.Connection, nombre: str
) -> Optional[dict]:
    """Return a user by exact name without password_hash, or None if not found."""
    async with db.execute(
        "SELECT id, nombre, is_admin FROM usuarios WHERE nombre = ?",
        (nombre,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def create_usuario(
    db: aiosqlite.Connection, nombre: str, password_hash: str, is_admin: bool
) -> int:
    """Insert a new user and return the new user id."""
    cursor = await db.execute(
        """
        INSERT INTO usuarios (nombre, password_hash, is_admin)
        VALUES (?, ?, ?)
        """,
        (nombre, password_hash, int(is_admin)),
    )
    await db.commit()
    return cursor.lastrowid


async def update_usuario(
    db: aiosqlite.Connection,
    usuario_id: int,
    nombre: Optional[str] = None,
    password_hash: Optional[str] = None,
    is_admin: Optional[bool] = None,
) -> Optional[dict]:
    """Update provided fields for a user. Returns the updated user without password_hash."""
    fields: list[str] = []
    params: list = []

    if nombre is not None:
        fields.append("nombre = ?")
        params.append(nombre)
    if password_hash is not None:
        fields.append("password_hash = ?")
        params.append(password_hash)
    if is_admin is not None:
        fields.append("is_admin = ?")
        params.append(int(is_admin))

    if not fields:
        return await get_usuario_by_id(db, usuario_id)

    params.append(usuario_id)
    await db.execute(
        f"UPDATE usuarios SET {', '.join(fields)} WHERE id = ?",
        tuple(params),
    )
    await db.commit()
    return await get_usuario_by_id(db, usuario_id)


async def delete_usuario(db: aiosqlite.Connection, usuario_id: int) -> bool:
    """Hard-delete a user. usuario_deposito rows are removed by CASCADE."""
    cursor = await db.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
    await db.commit()
    return cursor.rowcount > 0


async def count_admins(db: aiosqlite.Connection) -> int:
    """Return the number of global admins."""
    async with db.execute(
        "SELECT COUNT(*) FROM usuarios WHERE is_admin = 1"
    ) as cursor:
        row = await cursor.fetchone()
        return row[0]


async def assign_deposito(
    db: aiosqlite.Connection, usuario_id: int, deposito_id: int, role: str
) -> None:
    """Assign a depósito role to a user. Raises IntegrityError on duplicate."""
    await db.execute(
        """
        INSERT INTO usuario_deposito (usuario_id, deposito_id, role)
        VALUES (?, ?, ?)
        """,
        (usuario_id, deposito_id, role),
    )
    await db.commit()


async def unassign_deposito(
    db: aiosqlite.Connection, usuario_id: int, deposito_id: int
) -> bool:
    """Remove a depósito assignment. Returns True if a row was deleted."""
    cursor = await db.execute(
        "DELETE FROM usuario_deposito WHERE usuario_id = ? AND deposito_id = ?",
        (usuario_id, deposito_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_user_depositos(db: aiosqlite.Connection, usuario_id: int) -> list[dict]:
    """Return depósito assignments for a user."""
    async with db.execute(
        """
        SELECT ud.deposito_id, d.nombre AS deposito_nombre, ud.role
        FROM usuario_deposito ud
        JOIN depositos d ON d.id = ud.deposito_id
        WHERE ud.usuario_id = ?
        ORDER BY d.nombre
        """,
        (usuario_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_deposito_ids_for_user(
    db: aiosqlite.Connection, usuario_id: int
) -> list[int]:
    """Return the list of depósito IDs assigned to a user."""
    async with db.execute(
        "SELECT deposito_id FROM usuario_deposito WHERE usuario_id = ?",
        (usuario_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [row["deposito_id"] for row in rows]


async def get_user_role_for_deposito(
    db: aiosqlite.Connection, usuario_id: int, deposito_id: Optional[int]
) -> Optional[str]:
    """Return the user's role for a depósito, or None if not assigned."""
    if deposito_id is None:
        return None
    async with db.execute(
        "SELECT role FROM usuario_deposito WHERE usuario_id = ? AND deposito_id = ?",
        (usuario_id, deposito_id),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return row["role"]
