"""Deposito (warehouse) data access layer.

Depositos are hard-deleted. Deletion is guarded upstream: a deposito cannot be
removed while it has estantes assigned, and at least one deposito must remain.
`usuario_deposito` assignments cascade on delete (see migration 010).
"""

from typing import Optional

import aiosqlite


async def list_depositos_with_stats(
    db: aiosqlite.Connection,
    deposito_ids: Optional[list[int]] = None,
) -> list[dict]:
    """Return depositos with estantes/usuarios counts, ordered by name.

    Filtering contract (mirrors ``estante_repository.list_estantes``):
      - ``deposito_ids is None``  (admin): no filter, all depositos returned.
      - ``deposito_ids is []``    (non-admin, no access): returns ``[]``.
      - ``deposito_ids is [a,b]`` (non-admin, restricted): ``WHERE d.id IN (a, b)``.
    """
    if deposito_ids is not None and not deposito_ids:
        return []

    sql = """
        SELECT d.id,
               d.nombre,
               d.created_at,
               (SELECT COUNT(*) FROM estantes e
                  WHERE e.deposito_id = d.id AND e.deleted_at IS NULL) AS estantes_count,
               (SELECT COUNT(*) FROM usuario_deposito ud
                  WHERE ud.deposito_id = d.id) AS usuarios_count
        FROM depositos d
    """
    params: list = []
    if deposito_ids is not None:
        placeholders = ",".join("?" for _ in deposito_ids)
        sql += f" WHERE d.id IN ({placeholders})"
        params.extend(deposito_ids)
    sql += " ORDER BY d.nombre"

    async with db.execute(sql, tuple(params)) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_deposito_by_id(
    db: aiosqlite.Connection, deposito_id: int
) -> Optional[dict]:
    """Return a deposito by id, or None."""
    async with db.execute(
        "SELECT id, nombre, created_at FROM depositos WHERE id = ?",
        (deposito_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def get_deposito_by_name(
    db: aiosqlite.Connection, nombre: str
) -> Optional[dict]:
    """Return a deposito by exact name, or None.

    Used for duplicate-name checks on create and update.
    """
    async with db.execute(
        "SELECT id, nombre, created_at FROM depositos WHERE nombre = ?",
        (nombre,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def create_deposito(db: aiosqlite.Connection, nombre: str) -> int:
    """Insert a new deposito and return the new id.

    Raises ``sqlite3.IntegrityError`` on a duplicate name (UNIQUE constraint).
    """
    cursor = await db.execute(
        "INSERT INTO depositos (nombre) VALUES (?)",
        (nombre,),
    )
    await db.commit()
    return cursor.lastrowid


async def update_deposito(
    db: aiosqlite.Connection, deposito_id: int, nombre: str
) -> Optional[dict]:
    """Update a deposito's name. Returns the updated dict, or None if missing.

    Raises ``sqlite3.IntegrityError`` on a duplicate name (UNIQUE constraint).
    """
    cursor = await db.execute(
        "UPDATE depositos SET nombre = ? WHERE id = ?",
        (nombre, deposito_id),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return None
    return await get_deposito_by_id(db, deposito_id)


async def delete_deposito(db: aiosqlite.Connection, deposito_id: int) -> bool:
    """Hard-delete a deposito. ``usuario_deposito`` rows cascade on delete.

    Callers MUST guard: reject when the deposito has estantes (FK RESTRICT) or
    when it is the last remaining deposito.
    """
    cursor = await db.execute("DELETE FROM depositos WHERE id = ?", (deposito_id,))
    await db.commit()
    return cursor.rowcount > 0


async def count_estantes_for_deposito(
    db: aiosqlite.Connection, deposito_id: int
) -> int:
    """Return the number of estantes assigned to a deposito (including soft-deleted).

    The ``estantes.deposito_id`` FK has no ON DELETE clause, so SQLite blocks
    deletion when ANY estante — active or soft-deleted — still references the
    deposito.  We count all of them so the guard returns a clear 400 instead of
    letting the DELETE hit a 500 FK constraint error.
    """
    async with db.execute(
        "SELECT COUNT(*) FROM estantes WHERE deposito_id = ?",
        (deposito_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return row[0]


async def count_usuarios_for_deposito(
    db: aiosqlite.Connection, deposito_id: int
) -> int:
    """Return the number of users assigned to a deposito."""
    async with db.execute(
        "SELECT COUNT(*) FROM usuario_deposito WHERE deposito_id = ?",
        (deposito_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return row[0]


async def count_depositos(db: aiosqlite.Connection) -> int:
    """Return the total number of depositos."""
    async with db.execute("SELECT COUNT(*) FROM depositos") as cursor:
        row = await cursor.fetchone()
        return row[0]
