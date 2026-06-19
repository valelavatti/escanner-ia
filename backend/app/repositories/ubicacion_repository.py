"""Ubicacion (shelf cell) data access layer.

Each ubicacion belongs to an estante and represents a single physical cell.
QR values are generated adaptively based on the estante's dimensions so that
single-row, single-column, and single-cell shelves keep their QR labels short.
"""

from typing import Optional

import aiosqlite


class UbicacionOcupadaError(Exception):
    """Raised when trying to assign a product to a ubicacion that already has one."""


def generate_qr_valor(estante_nombre: str, fila: int, columna: int, filas: int, columnas: int) -> str:
    """Generate an adaptive QR value based on the shelf shape.

    - 1x1 shelf: just the shelf name (e.g. "Suelto").
    - Single-row shelf: only the column matters (e.g. "A-C5").
    - Single-column shelf: only the row matters (e.g. "A-F3").
    - 2D grid: full row + column (e.g. "A-F1-C2").
    """
    if filas == 1 and columnas == 1:
        return estante_nombre
    elif filas == 1:
        return f"{estante_nombre}-C{columna}"
    elif columnas == 1:
        return f"{estante_nombre}-F{fila}"
    else:
        return f"{estante_nombre}-F{fila}-C{columna}"


async def auto_generate_ubicaciones(
    db: aiosqlite.Connection,
    estante_id: int,
    estante_nombre: str,
    filas: int,
    columnas: int,
) -> int:
    """Idempotently create all cells for an estante grid.

    Existing cells are left untouched (INSERT OR IGNORE). Returns the number of
    newly created ubicaciones.
    """
    if filas < 1 or columnas < 1:
        return 0

    valores = []
    for fila in range(1, filas + 1):
        for columna in range(1, columnas + 1):
            qr_valor = generate_qr_valor(estante_nombre, fila, columna, filas, columnas)
            valores.append((estante_id, fila, columna, qr_valor))

    placeholders = ",".join("(?, ?, ?, ?)" for _ in valores)
    flat = [item for sublist in valores for item in sublist]

    await db.execute(
        f"""
        INSERT OR IGNORE INTO ubicaciones (estante_id, fila, columna, qr_valor)
        VALUES {placeholders}
        """,
        flat,
    )

    async with db.execute("SELECT changes()") as cursor:
        row = await cursor.fetchone()
        return row[0] if row else 0


async def list_ubicaciones_by_estante(db: aiosqlite.Connection, estante_id: int) -> list[dict]:
    """Return all ubicaciones for an estante, ordered by row then column."""
    async with db.execute(
        """
        SELECT
            u.id,
            u.estante_id,
            u.fila,
            u.columna,
            u.producto_id,
            u.stock_actual,
            u.qr_valor,
            u.estado,
            p.sku AS producto_sku,
            p.descripcion AS producto_descripcion,
            e.nombre AS estante_nombre
        FROM ubicaciones u
        JOIN estantes e ON e.id = u.estante_id
        LEFT JOIN productos p ON p.sku = u.producto_id
        WHERE u.estante_id = ?
        ORDER BY u.fila, u.columna
        """,
        (estante_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_ubicacion_by_id(db: aiosqlite.Connection, ubicacion_id: int) -> Optional[dict]:
    """Return a single ubicacion by id, or None."""
    async with db.execute(
        """
        SELECT
            u.id,
            u.estante_id,
            u.fila,
            u.columna,
            u.producto_id,
            u.stock_actual,
            u.qr_valor,
            u.estado,
            p.sku AS producto_sku,
            p.descripcion AS producto_descripcion,
            e.nombre AS estante_nombre
        FROM ubicaciones u
        JOIN estantes e ON e.id = u.estante_id
        LEFT JOIN productos p ON p.sku = u.producto_id
        WHERE u.id = ?
        """,
        (ubicacion_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def get_ubicacion_by_qr(db: aiosqlite.Connection, qr_valor: str) -> Optional[dict]:
    """Return an active ubicacion by QR value, joining its estante info.

    Soft-deleted estantes and out-of-bounds cells are excluded so scanners only
    anchor to valid, active locations.
    """
    async with db.execute(
        """
        SELECT
            u.id,
            u.estante_id,
            u.fila,
            u.columna,
            u.producto_id,
            u.stock_actual,
            u.qr_valor,
            u.estado,
            p.sku AS producto_sku,
            p.descripcion AS producto_descripcion,
            e.nombre AS estante_nombre
        FROM ubicaciones u
        JOIN estantes e ON e.id = u.estante_id
        LEFT JOIN productos p ON p.sku = u.producto_id
        WHERE u.qr_valor = ?
          AND u.estado = 'activo'
          AND e.deleted_at IS NULL
        """,
        (qr_valor,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def assign_producto_to_ubicacion(
    db: aiosqlite.Connection,
    ubicacion_id: int,
    producto_id: str,
) -> bool:
    """Assign a product SKU to an empty ubicacion.

    Raises:
        UbicacionOcupadaError: if the ubicacion already has a product assigned.
    """
    async with db.execute(
        "SELECT producto_id FROM ubicaciones WHERE id = ?",
        (ubicacion_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return False

    if row["producto_id"] is not None:
        raise UbicacionOcupadaError("La ubicacion ya tiene un producto asignado")

    await db.execute(
        """
        UPDATE ubicaciones
        SET producto_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (producto_id, ubicacion_id),
    )
    await db.commit()
    return True


async def get_out_of_bounds_ubicaciones(
    db: aiosqlite.Connection,
    estante_id: int,
    new_filas: int,
    new_columnas: int,
) -> list[dict]:
    """Return ubicaciones that fall outside the new estante dimensions."""
    async with db.execute(
        """
        SELECT
            u.id,
            u.estante_id,
            u.fila,
            u.columna,
            u.producto_id,
            u.stock_actual,
            u.qr_valor,
            u.estado,
            p.sku AS producto_sku,
            p.descripcion AS producto_descripcion,
            e.nombre AS estante_nombre
        FROM ubicaciones u
        JOIN estantes e ON e.id = u.estante_id
        LEFT JOIN productos p ON p.sku = u.producto_id
        WHERE u.estante_id = ?
          AND (u.fila > ? OR u.columna > ?)
        ORDER BY u.fila, u.columna
        """,
        (estante_id, new_filas, new_columnas),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def hard_delete_ubicaciones(
    db: aiosqlite.Connection,
    ubicacion_ids: list[int],
) -> int:
    """Hard delete the listed ubicaciones after explicit user confirmation."""
    if not ubicacion_ids:
        return 0

    placeholders = ",".join("?" for _ in ubicacion_ids)
    cursor = await db.execute(
        f"DELETE FROM ubicaciones WHERE id IN ({placeholders})",
        tuple(ubicacion_ids),
    )
    await db.commit()
    return cursor.rowcount
