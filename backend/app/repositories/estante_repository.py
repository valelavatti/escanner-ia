"""Estante (shelf) data access layer.

Estantes are soft-deleted so that audit history (`movimientos`) remains valid.
Creating or resizing an estante auto-generates or flags its `ubicaciones` cells.
"""

from typing import Optional

import aiosqlite

from app.repositories import ubicacion_repository


async def list_estantes(db: aiosqlite.Connection, include_deleted: bool = False) -> list[dict]:
    """Return all estantes ordered by visual order, optionally including soft-deleted ones."""
    sql = """
        SELECT e.*,
               (SELECT COUNT(*) FROM ubicaciones u WHERE u.estante_id = e.id) AS ubicaciones_count
        FROM estantes e
    """
    params: tuple = ()

    if not include_deleted:
        sql += " WHERE e.deleted_at IS NULL"

    sql += " ORDER BY e.orden_visual, e.id"

    async with db.execute(sql, params) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_estante_by_id(db: aiosqlite.Connection, estante_id: int) -> Optional[dict]:
    """Return a non-deleted estante by id, or None."""
    async with db.execute(
        "SELECT * FROM estantes WHERE id = ? AND deleted_at IS NULL",
        (estante_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def get_estante_by_name(db: aiosqlite.Connection, nombre: str) -> Optional[dict]:
    """Return a non-deleted estante by exact name, or None.

    Used for duplicate-name checks when creating a new estante.
    """
    async with db.execute(
        "SELECT * FROM estantes WHERE nombre = ? AND deleted_at IS NULL",
        (nombre,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def create_estante(
    db: aiosqlite.Connection,
    nombre: str,
    orden_visual: int,
    filas: int,
    columnas: int,
) -> int:
    """Insert a new estante and auto-generate its ubicaciones.

    The whole operation is wrapped in a transaction so a failure to generate
    cells rolls back the estante insert.
    """
    try:
        await db.execute("BEGIN")
        cursor = await db.execute(
            """
            INSERT INTO estantes (nombre, orden_visual, filas, columnas)
            VALUES (?, ?, ?, ?)
            """,
            (nombre, orden_visual, filas, columnas),
        )
        estante_id = cursor.lastrowid
        await ubicacion_repository.auto_generate_ubicaciones(
            db, estante_id, nombre, filas, columnas
        )
        await db.commit()
        return estante_id
    except Exception:
        await db.rollback()
        raise


async def update_estante_dimensions(
    db: aiosqlite.Connection,
    estante_id: int,
    filas: int,
    columnas: int,
) -> Optional[dict]:
    """Update an estante's grid dimensions.

    - Expanding the grid generates new cells and reactivates previously
      out-of-bounds cells that now fall inside the new bounds.
    - Shrinking the grid flags out-of-bounds cells as `fuera_de_rango` but
      never deletes them.

    Returns the updated estante dict, or None if it does not exist.
    """
    current = await get_estante_by_id(db, estante_id)
    if current is None:
        return None

    old_filas = current["filas"]
    old_columnas = current["columnas"]

    try:
        await db.execute("BEGIN")
        await db.execute(
            """
            UPDATE estantes
            SET filas = ?, columnas = ?
            WHERE id = ? AND deleted_at IS NULL
            """,
            (filas, columnas, estante_id),
        )

        expanded = filas > old_filas or columnas > old_columnas
        shrunk = filas < old_filas or columnas < old_columnas

        if expanded:
            await ubicacion_repository.auto_generate_ubicaciones(
                db, estante_id, current["nombre"], filas, columnas
            )
            # Reactivate cells that were previously flagged but are now in bounds.
            await db.execute(
                """
                UPDATE ubicaciones
                SET estado = 'activo', updated_at = CURRENT_TIMESTAMP
                WHERE estante_id = ?
                  AND estado = 'fuera_de_rango'
                  AND fila <= ?
                  AND columna <= ?
                """,
                (estante_id, filas, columnas),
            )

        if shrunk:
            await db.execute(
                """
                UPDATE ubicaciones
                SET estado = 'fuera_de_rango', updated_at = CURRENT_TIMESTAMP
                WHERE estante_id = ?
                  AND (fila > ? OR columna > ?)
                  AND estado != 'fuera_de_rango'
                """,
                (estante_id, filas, columnas),
            )

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return await get_estante_by_id(db, estante_id)


async def update_estante_orden(
    db: aiosqlite.Connection,
    estante_id: int,
    orden_visual: int,
) -> Optional[dict]:
    """Update only the visual order of an estante."""
    cursor = await db.execute(
        "UPDATE estantes SET orden_visual = ? WHERE id = ? AND deleted_at IS NULL",
        (orden_visual, estante_id),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return None
    return await get_estante_by_id(db, estante_id)


async def soft_delete_estante(db: aiosqlite.Connection, estante_id: int) -> bool:
    """Soft delete an estante, preserving all ubicaciones and movimientos."""
    cursor = await db.execute(
        """
        UPDATE estantes
        SET deleted_at = CURRENT_TIMESTAMP
        WHERE id = ? AND deleted_at IS NULL
        """,
        (estante_id,),
    )
    await db.commit()
    return cursor.rowcount > 0
