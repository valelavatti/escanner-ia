"""Ubicacion (shelf cell) data access layer.

Each ubicacion belongs to an estante and represents a single physical cell.
QR values are generated adaptively based on the estante's dimensions so that
single-row, single-column, and single-cell shelves keep their QR labels short.
"""

from typing import Optional

import aiosqlite

from app.repositories import movimiento_repository as _mov_repo


class UbicacionOcupadaError(Exception):
    """Raised when trying to assign a product to a ubicacion that already has one."""


def _to_alpha(n: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA (Excel-style bijective base-26)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def format_axis_label(index: int, fmt: str) -> str:
    """Format a 1-based label index as numeric or Excel-style alpha."""
    return _to_alpha(index) if fmt == "alpha" else str(index)


def effective_label_index(position: int, size: int, order: str) -> int:
    """Map a stored grid position to its label index given the axis direction."""
    return size - position + 1 if order in ("bottom_up", "right_left") else position


def compute_labels(row: dict) -> tuple[str, str]:
    """Return (fila_label, columna_label) for a ubicacion row carrying estante config.

    Uses the estante's total dimensions (``estante_filas``/``estante_columnas``)
    for reversed axes; falls back to the raw position (identity mapping) when
    the row does not carry the config columns.
    """
    fila_label = format_axis_label(
        effective_label_index(
            row["fila"],
            row.get("estante_filas") or row["fila"],
            row.get("fila_order") or "top_down",
        ),
        row.get("fila_format") or "numeric",
    )
    columna_label = format_axis_label(
        effective_label_index(
            row["columna"],
            row.get("estante_columnas") or row["columna"],
            row.get("columna_order") or "left_right",
        ),
        row.get("columna_format") or "numeric",
    )
    return fila_label, columna_label


def generate_qr_valor(
    estante_nombre: str,
    fila: int,
    columna: int,
    filas: int,
    columnas: int,
    fila_order: str = "top_down",
    columna_order: str = "left_right",
    fila_format: str = "numeric",
    columna_format: str = "numeric",
) -> str:
    """Generate an adaptive QR value based on the shelf shape.

    - 1x1 shelf: just the shelf name (e.g. "Suelto").
    - Single-row shelf: only the column matters (e.g. "A-C5").
    - Single-column shelf: only the row matters (e.g. "A-F3").
    - 2D grid: full row + column (e.g. "A-F1-C2").

    The stored fila/columna are grid coordinates; the label config only changes
    the human-readable label embedded in the QR value. Defaults reproduce the
    historic top-down, left-to-right, numeric labeling.
    """
    fila_label = format_axis_label(
        effective_label_index(fila, filas, fila_order), fila_format
    )
    columna_label = format_axis_label(
        effective_label_index(columna, columnas, columna_order), columna_format
    )
    if filas == 1 and columnas == 1:
        return estante_nombre
    elif filas == 1:
        return f"{estante_nombre}-C{columna_label}"
    elif columnas == 1:
        return f"{estante_nombre}-F{fila_label}"
    else:
        return f"{estante_nombre}-F{fila_label}-C{columna_label}"


async def auto_generate_ubicaciones(
    db: aiosqlite.Connection,
    estante_id: int,
    estante_nombre: str,
    filas: int,
    columnas: int,
    fila_order: str = "top_down",
    columna_order: str = "left_right",
    fila_format: str = "numeric",
    columna_format: str = "numeric",
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
            qr_valor = generate_qr_valor(
                estante_nombre, fila, columna, filas, columnas,
                fila_order=fila_order,
                columna_order=columna_order,
                fila_format=fila_format,
                columna_format=columna_format,
            )
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
            e.nombre AS estante_nombre,
            e.filas AS estante_filas,
            e.columnas AS estante_columnas,
            e.fila_order,
            e.columna_order,
            e.fila_format,
            e.columna_format
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
            e.nombre AS estante_nombre,
            e.deposito_id,
            e.filas AS estante_filas,
            e.columnas AS estante_columnas,
            e.fila_order,
            e.columna_order,
            e.fila_format,
            e.columna_format
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
            e.nombre AS estante_nombre,
            e.deposito_id,
            e.filas AS estante_filas,
            e.columnas AS estante_columnas,
            e.fila_order,
            e.columna_order,
            e.fila_format,
            e.columna_format
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
    usuario_id: int,
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

    # Append-only audit record for the assignment (no stock change).
    stock_general = await _mov_repo.get_producto_stock_total(db, producto_id)
    await db.execute(
        """
        INSERT INTO movimientos
            (usuario_id, producto_id, ubicacion_id, cantidad, stock_anterior, stock_nuevo, tipo,
             stock_general_anterior, stock_general_nuevo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (usuario_id, producto_id, ubicacion_id, 0, 0, 0, "asignacion",
         stock_general, stock_general),
    )

    await db.commit()
    return True


async def unassign_producto_from_ubicacion(
    db: aiosqlite.Connection,
    ubicacion_id: int,
    usuario_id: int,
) -> bool:
    """Remove the product assignment from a ubicacion (set producto_id = NULL).

    The ubicacion's stock_actual is NOT reset — it stays at whatever the last
    movimiento left. If the user wants to zero it out, they scan and enter 0.
    Returns True if the ubicacion existed, False otherwise.
    """
    async with db.execute(
        "SELECT producto_id, stock_actual FROM ubicaciones WHERE id = ?",
        (ubicacion_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return False

    old_producto_id = row["producto_id"]
    stock_anterior = row["stock_actual"]

    await db.execute(
        """
        UPDATE ubicaciones
        SET producto_id = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (ubicacion_id,),
    )

    # Append-only audit record for the removal (stock conceptually reset to 0).
    if old_producto_id is not None:
        stock_general = await _mov_repo.get_producto_stock_total(db, old_producto_id)
        await db.execute(
            """
            INSERT INTO movimientos
                (usuario_id, producto_id, ubicacion_id, cantidad, stock_anterior, stock_nuevo, tipo,
                 stock_general_anterior, stock_general_nuevo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (usuario_id, old_producto_id, ubicacion_id, 0, stock_anterior, 0, "desasignacion",
             stock_general, stock_general),
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
            e.nombre AS estante_nombre,
            e.filas AS estante_filas,
            e.columnas AS estante_columnas,
            e.fila_order,
            e.columna_order,
            e.fila_format,
            e.columna_format
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
