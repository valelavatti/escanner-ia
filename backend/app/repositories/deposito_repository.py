"""Deposito (warehouse) data access layer.

Depositos are hard-deleted. Deletion is guarded upstream: a deposito cannot be
removed while it has ACTIVE estantes assigned, and at least one deposito must
remain. Soft-deleted estantes WITHOUT movimientos can be force-deleted along
with the deposito by passing ``cascade=True`` to ``delete_deposito``; those
WITH movimientos always block (audit trail must be preserved).
``usuario_deposito`` assignments cascade on delete (see migration 010).
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


async def delete_deposito(
    db: aiosqlite.Connection,
    deposito_id: int,
    cascade: bool = False,
) -> dict:
    """Hard-delete a deposito, optionally cascading soft-deleted estantes.

    ``usuario_deposito`` rows cascade on delete (migration 010).

    Args:
        db: Configured aiosqlite connection.
        deposito_id: Id of the deposito to delete.
        cascade: When True, hard-delete soft-deleted estantes that have no
            movimientos (cascades to their ubicaciones and qr_cache files)
            before deleting the deposito. Active estantes and soft-deleted
            estantes WITH movimientos always block, regardless of this flag.

    Returns:
        ``{'ok': True, 'deleted_estantes': N, 'qr_files': M}`` on success.
        ``{'ok': False, 'error': <code>}`` when deletion is blocked, where
        ``<code>`` is one of:

        - ``active_estantes`` — the deposito has active estantes; the caller
          must move or soft-delete them first.
        - ``soft_deleted_with_movs`` — the deposito has soft-deleted estantes
          that still have movimientos; the audit trail must be preserved.
        - ``soft_deleted_without_movs`` — the deposito has soft-deleted
          estantes without movimientos; the caller should retry with
          ``cascade=True`` (or surface a hint to that effect).
        - ``not_found`` — the deposito row was gone by the time the DELETE
          ran (caller should have checked existence separately).
    """
    breakdown = await get_estantes_breakdown(db, deposito_id)

    if breakdown["active"] > 0:
        return {"ok": False, "error": "active_estantes"}
    if breakdown["soft_deleted_with_movs"] > 0:
        return {"ok": False, "error": "soft_deleted_with_movs"}

    estante_ids_to_cascade: list[int] = []
    if breakdown["soft_deleted_without_movs"] > 0:
        if not cascade:
            return {"ok": False, "error": "soft_deleted_without_movs"}
        estante_ids_to_cascade = await _soft_deleted_estantes_without_movs(
            db, deposito_id
        )

    # Snapshot qr_valores before deleting so we can clean the qr_cache after
    # the commit (best-effort, never blocks the DB transaction).
    qr_valores: list[str] = []
    if estante_ids_to_cascade:
        placeholders = ",".join("?" for _ in estante_ids_to_cascade)
        async with db.execute(
            f"SELECT qr_valor FROM ubicaciones WHERE estante_id IN ({placeholders})",
            tuple(estante_ids_to_cascade),
        ) as cursor:
            qr_valores = [r[0] for r in await cursor.fetchall()]

    await db.execute("BEGIN")
    try:
        if estante_ids_to_cascade:
            placeholders = ",".join("?" for _ in estante_ids_to_cascade)
            # Order matters: ubicaciones first (FK ON DELETE RESTRICT from
            # movimientos AND from estantes), then estantes, then deposito.
            await db.execute(
                f"DELETE FROM ubicaciones WHERE estante_id IN ({placeholders})",
                tuple(estante_ids_to_cascade),
            )
            await db.execute(
                f"DELETE FROM estantes WHERE id IN ({placeholders})",
                tuple(estante_ids_to_cascade),
            )
        cursor = await db.execute(
            "DELETE FROM depositos WHERE id = ?",
            (deposito_id,),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Best-effort qr_cache cleanup (outside the DB transaction).
    qr_files = 0
    if qr_valores:
        from app.services import qr as qr_service
        for qr_valor in qr_valores:
            qr_files += qr_service.delete_qr_cache_for(qr_valor)

    if cursor.rowcount == 0:
        return {"ok": False, "error": "not_found"}

    return {
        "ok": True,
        "deleted_estantes": len(estante_ids_to_cascade),
        "qr_files": qr_files,
    }


async def get_estantes_breakdown(
    db: aiosqlite.Connection, deposito_id: int
) -> dict:
    """Categorize a deposito's estantes for the delete-guard.

    Returns a dict with three counts:

    - ``active``: ``deleted_at IS NULL`` — always blocks deposito deletion.
    - ``soft_deleted_with_movs``: ``deleted_at IS NOT NULL`` AND at least one
      of its ubicaciones has a movimiento — always blocks (audit trail).
    - ``soft_deleted_without_movs``: ``deleted_at IS NOT NULL`` AND no
      movimientos anywhere — blocks unless ``cascade=True`` is passed.
    """
    async with db.execute(
        """
        SELECT
            e.id,
            e.deleted_at,
            EXISTS (
                SELECT 1 FROM movimientos m
                JOIN ubicaciones u ON u.id = m.ubicacion_id
                WHERE u.estante_id = e.id
            ) AS has_movs
        FROM estantes e
        WHERE e.deposito_id = ?
        """,
        (deposito_id,),
    ) as cursor:
        rows = await cursor.fetchall()

    active = 0
    soft_with_movs = 0
    soft_without_movs = 0
    for row in rows:
        if row["deleted_at"] is None:
            active += 1
        elif row["has_movs"]:
            soft_with_movs += 1
        else:
            soft_without_movs += 1
    return {
        "active": active,
        "soft_deleted_with_movs": soft_with_movs,
        "soft_deleted_without_movs": soft_without_movs,
    }


async def _soft_deleted_estantes_without_movs(
    db: aiosqlite.Connection, deposito_id: int
) -> list[int]:
    """Return ids of soft-deleted estantes of ``deposito_id`` with no movimientos."""
    async with db.execute(
        """
        SELECT e.id FROM estantes e
        WHERE e.deposito_id = ? AND e.deleted_at IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM movimientos m
              JOIN ubicaciones u ON u.id = m.ubicacion_id
              WHERE u.estante_id = e.id
          )
        """,
        (deposito_id,),
    ) as cursor:
        return [r[0] for r in await cursor.fetchall()]


async def hard_delete_estante_cascade(
    db: aiosqlite.Connection, estante_id: int
) -> dict:
    """Hard-delete an estante, its ubicaciones, and qr_cache PNG files.

    Caller MUST verify the estante has no movimientos referencing its
    ubicaciones — ``movimientos.ubicacion_id`` is ``ON DELETE RESTRICT`` and
    will raise ``IntegrityError`` otherwise.

    Returns ``{'ubicaciones': N, 'qr_files': M}``.
    """
    async with db.execute(
        "SELECT qr_valor FROM ubicaciones WHERE estante_id = ?",
        (estante_id,),
    ) as cursor:
        qr_valores = [r[0] for r in await cursor.fetchall()]

    await db.execute("BEGIN")
    try:
        await db.execute(
            "DELETE FROM ubicaciones WHERE estante_id = ?",
            (estante_id,),
        )
        await db.execute("DELETE FROM estantes WHERE id = ?", (estante_id,))
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    from app.services import qr as qr_service
    qr_files = 0
    for qr_valor in qr_valores:
        qr_files += qr_service.delete_qr_cache_for(qr_valor)

    return {"ubicaciones": len(qr_valores), "qr_files": qr_files}


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
