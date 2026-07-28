"""Movimiento (stock movement) data access layer.

This is the core of the append-only audit trail. Every stock change creates a
single ``movimientos`` record inside a transaction that also updates the
location's current stock (or sums into the Suelto catch-all shelf).
"""

import asyncio
import csv
import io
import sqlite3
from typing import Optional

import aiosqlite


class NegativeStockError(Exception):
    """Raised when a movement would result in negative stock."""


class DatabaseBusyError(Exception):
    """Raised when the SQLite write lock cannot be acquired after all retries."""


class ProductoNotFoundError(Exception):
    """Raised when the requested product SKU does not exist."""


class UbicacionNotFoundError(Exception):
    """Raised when the requested ubicacion does not exist."""


_MAX_RETRIES = 3
_RETRY_DELAYS_MS = [50, 100, 200]


async def _fetch_one_row(db: aiosqlite.Connection, sql: str, params: tuple) -> Optional[dict]:
    """Helper to fetch a single row as a dict."""
    async with db.execute(sql, params) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def _is_suelto(db: aiosqlite.Connection, ubicacion_id: int) -> bool:
    """Return True if the ubicacion belongs to the 'Suelto' estante."""
    row = await _fetch_one_row(
        db,
        """
        SELECT e.nombre AS estante_nombre
        FROM ubicaciones u
        JOIN estantes e ON e.id = u.estante_id
        WHERE u.id = ?
        """,
        (ubicacion_id,),
    )
    return row is not None and row.get("estante_nombre") == "Suelto"


async def _get_stock_anterior(
    db: aiosqlite.Connection,
    producto_sku: str,
    ubicacion_id: int,
    es_suelto: bool,
) -> int:
    """Return the stock before a movement.

    For the Suelto catch-all shelf, stock is the sum of all movements for that
    product in that location. For regular shelves, stock comes from
    ``ubicaciones.stock_actual``.
    """
    if es_suelto:
        row = await _fetch_one_row(
            db,
            """
            SELECT COALESCE(SUM(cantidad), 0) AS stock
            FROM movimientos
            WHERE producto_id = ? AND ubicacion_id = ?
            """,
            (producto_sku, ubicacion_id),
        )
        return int(row["stock"]) if row else 0

    row = await _fetch_one_row(
        db,
        "SELECT producto_id, stock_actual FROM ubicaciones WHERE id = ?",
        (ubicacion_id,),
    )
    if row is None:
        raise UbicacionNotFoundError(f"Ubicacion {ubicacion_id} no encontrada")
    # If the location has a DIFFERENT product assigned, this is a reassignment —
    # stock starts fresh at 0 for the new product.
    if row["producto_id"] and row["producto_id"] != producto_sku:
        return 0
    return int(row["stock_actual"])


async def _create_movimiento_once(
    db: aiosqlite.Connection,
    usuario_id: int,
    producto_sku: str,
    ubicacion_id: int,
    cantidad: int,
    tipo: str,
) -> dict:
    """Execute a single stock movement transaction (no retry wrapping)."""
    if tipo not in ("alta", "ajuste"):
        raise ValueError("tipo debe ser 'alta' o 'ajuste'")

    await db.execute("BEGIN")
    try:
        # Validate referenced product exists (inside transaction for consistency).
        producto = await _fetch_one_row(
            db,
            "SELECT sku, descripcion FROM productos WHERE sku = ?",
            (producto_sku,),
        )
        if producto is None:
            raise ProductoNotFoundError(f"Producto {producto_sku} no encontrado")

        # Validate referenced location exists and load its shelf context.
        ubicacion = await _fetch_one_row(
            db,
            """
            SELECT
                u.id,
                u.estante_id,
                u.fila,
                u.columna,
                u.producto_id,
                u.stock_actual,
                u.qr_valor,
                e.nombre AS estante_nombre
            FROM ubicaciones u
            JOIN estantes e ON e.id = u.estante_id
            WHERE u.id = ?
            """,
            (ubicacion_id,),
        )
        if ubicacion is None:
            raise UbicacionNotFoundError(f"Ubicacion {ubicacion_id} no encontrada")

        es_suelto = ubicacion["estante_nombre"] == "Suelto"

        # Snapshot the product's general stock BEFORE any changes in this TX.
        stock_general_anterior = await get_producto_stock_total(db, producto_sku)

        # Read stock inside the transaction so concurrent writers serialize
        # and the second movement sees the updated stock from the first.
        stock_anterior = await _get_stock_anterior(db, producto_sku, ubicacion_id, es_suelto)

        # Calculate new stock.
        if tipo == "alta":
            stock_nuevo = stock_anterior + cantidad
            cantidad_registrada = cantidad
        else:  # ajuste: cantidad is the new absolute stock
            stock_nuevo = cantidad
            cantidad_registrada = cantidad - stock_anterior

        if stock_nuevo < 0:
            raise NegativeStockError("El stock no puede ser negativo")

        # Track assignment/desasignacion BEFORE the stock movement (all in same TX).
        old_producto_id = ubicacion["producto_id"]
        is_new_assignment = old_producto_id is None and producto_sku is not None and not es_suelto
        is_reassignment = (
            old_producto_id is not None
            and old_producto_id != producto_sku
            and not es_suelto
        )

        if is_reassignment:
            # Slice 2b audit-mis-attribution fix (REQ-B-003 + B5): the
            # desasignacion row is the OUTGOING product's audit record.
            # Snapshot the OLD product's stock_general BEFORE any
            # ubicacion mutation takes effect — the ``stock_general_anterior``
            # captured at line 145 above is the NEW product's snapshot and was
            # being used here incorrectly for the OLD product's audit row
            # (the mis-attribution bug at the original lines 171-184).
            old_producto_stock_general_anterior = await get_producto_stock_total(
                db, old_producto_id
            )
            old_producto_stock_general_nuevo = (
                old_producto_stock_general_anterior - ubicacion["stock_actual"]
            )
            await db.execute(
                """
                INSERT INTO movimientos (usuario_id, producto_id, ubicacion_id,
                    cantidad, stock_anterior, stock_nuevo, tipo,
                    stock_general_anterior, stock_general_nuevo)
                VALUES (?, ?, ?, 0, ?, 0, 'desasignacion', ?, ?)
                """,
                (
                    usuario_id, old_producto_id, ubicacion_id,
                    ubicacion["stock_actual"],
                    old_producto_stock_general_anterior,
                    old_producto_stock_general_nuevo,
                ),
            )

        if is_new_assignment or is_reassignment:
            await db.execute(
                """
                INSERT INTO movimientos (usuario_id, producto_id, ubicacion_id,
                    cantidad, stock_anterior, stock_nuevo, tipo,
                    stock_general_anterior, stock_general_nuevo)
                VALUES (?, ?, ?, 0, 0, 0, 'asignacion', ?, ?)
                """,
                (
                    usuario_id, producto_sku, ubicacion_id,
                    stock_general_anterior, stock_general_anterior,
                ),
            )

        # Calculate stock general after the stock change.
        stock_general_nuevo = stock_general_anterior + (stock_nuevo - stock_anterior)

        # Insert the immutable audit record for the stock change.
        cursor = await db.execute(
            """
            INSERT INTO movimientos
                (usuario_id, producto_id, ubicacion_id, cantidad,
                 stock_anterior, stock_nuevo, tipo,
                 stock_general_anterior, stock_general_nuevo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usuario_id,
                producto_sku,
                ubicacion_id,
                cantidad_registrada,
                stock_anterior,
                stock_nuevo,
                tipo,
                stock_general_anterior,
                stock_general_nuevo,
            ),
        )
        movimiento_id = cursor.lastrowid

        if not es_suelto:
            # Regular shelf: update its single-product stock.
            await db.execute(
                """
                UPDATE ubicaciones
                SET stock_actual = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (stock_nuevo, ubicacion_id),
            )
            # Auto-assign or reassign product on scan.
            if ubicacion["producto_id"] is None or ubicacion["producto_id"] != producto_sku:
                await db.execute(
                    """
                    UPDATE ubicaciones
                    SET producto_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (producto_sku, ubicacion_id),
                )

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    movimiento = await get_movimiento_by_id(db, movimiento_id)
    if movimiento is None:
        raise RuntimeError("Movimiento recien creado no encontrado")
    return movimiento


async def create_movimiento(
    db: aiosqlite.Connection,
    usuario_id: int,
    producto_sku: str,
    ubicacion_id: int,
    cantidad: int,
    tipo: str = "alta",
) -> dict:
    """Create a stock movement with SQLITE_BUSY retry.

    Args:
        db: Configured aiosqlite connection.
        usuario_id: ID of the user performing the movement.
        producto_sku: SKU of the affected product.
        ubicacion_id: ID of the affected location.
        cantidad: For ``alta``, amount to add. For ``ajuste``, new absolute stock.
        tipo: ``alta`` or ``ajuste``.

    Returns:
        The created movement record with joined display fields.

    Raises:
        ProductoNotFoundError: If the SKU does not exist.
        UbicacionNotFoundError: If the location does not exist.
        NegativeStockError: If the movement would result in negative stock.
        DatabaseBusyError: If SQLite remains locked after all retries.
    """
    last_error: Optional[Exception] = None
    for attempt, delay_ms in zip(range(_MAX_RETRIES), _RETRY_DELAYS_MS):
        try:
            return await _create_movimiento_once(
                db, usuario_id, producto_sku, ubicacion_id, cantidad, tipo
            )
        except sqlite3.OperationalError as exc:
            last_error = exc
            if "database is locked" not in str(exc).lower():
                raise
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(delay_ms / 1000.0)
        except Exception:
            # Non-busy errors are not retried.
            raise

    raise DatabaseBusyError(
        "Base de datos ocupada, intente nuevamente"
    ) from last_error


async def get_movimiento_by_id(db: aiosqlite.Connection, movimiento_id: int) -> Optional[dict]:
    """Return a single movement with joined display fields, or None."""
    async with db.execute(
        """
        SELECT
            m.id,
            m.usuario_id,
            u.nombre AS usuario_nombre,
            m.producto_id AS producto_sku,
            p.descripcion AS producto_descripcion,
            m.ubicacion_id,
            ubi.qr_valor AS ubicacion_qr,
            e.nombre AS estante_nombre,
            e.deposito_id,
            ubi.fila,
            ubi.columna,
            e.filas AS estante_filas,
            e.columnas AS estante_columnas,
            e.fila_order,
            e.columna_order,
            e.fila_format,
            e.columna_format,
            m.cantidad,
            m.stock_anterior,
            m.stock_nuevo,
            m.stock_general_anterior,
            m.stock_general_nuevo,
            m.timestamp,
            m.tipo
        FROM movimientos m
        LEFT JOIN usuarios u ON u.id = m.usuario_id
        LEFT JOIN productos p ON p.sku = m.producto_id
        JOIN ubicaciones ubi ON ubi.id = m.ubicacion_id
        JOIN estantes e ON e.id = ubi.estante_id
        WHERE m.id = ?
        """,
        (movimiento_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_producto_ubicacion_stock(
    db: aiosqlite.Connection,
    producto_sku: str,
    ubicacion_id: int,
) -> dict:
    """Return stock and assignment info for a product at a location.

    Returns a dict with ``stock_actual``, ``is_assigned`` and ``es_suelto``.
    For Suelto the shelf is always considered assigned and stock is the sum
    of movements. For regular shelves stock is ``ubicaciones.stock_actual``
    only when the product is assigned to that cell; otherwise stock is 0.
    """
    ubicacion = await _fetch_one_row(
        db,
        """
        SELECT u.id, u.producto_id, u.stock_actual, e.nombre AS estante_nombre
        FROM ubicaciones u
        JOIN estantes e ON e.id = u.estante_id
        WHERE u.id = ?
        """,
        (ubicacion_id,),
    )
    if ubicacion is None:
        raise UbicacionNotFoundError(f"Ubicacion {ubicacion_id} no encontrada")

    es_suelto = ubicacion["estante_nombre"] == "Suelto"
    stock = await _get_stock_anterior(db, producto_sku, ubicacion_id, es_suelto)

    if es_suelto:
        is_assigned = True
        existing_producto_sku = None
    else:
        is_assigned = ubicacion["producto_id"] == producto_sku
        if not is_assigned:
            stock = 0
        # If the location has a different product, return its SKU so the
        # frontend can warn the user before reassigning.
        existing_producto_sku = (
            ubicacion["producto_id"]
            if ubicacion["producto_id"] and ubicacion["producto_id"] != producto_sku
            else None
        )

    # Live stock of the product currently occupying the location. These are
    # the units that would silently vanish from that product's stock total if
    # the location gets reassigned to the scanned product.
    existing_producto_stock = (
        ubicacion["stock_actual"] if existing_producto_sku is not None else None
    )

    return {
        "stock_actual": stock,
        "is_assigned": is_assigned,
        "es_suelto": es_suelto,
        "existing_producto_sku": existing_producto_sku,
        "existing_producto_stock": existing_producto_stock,
    }


async def get_stock_by_producto_in_ubicacion(
    db: aiosqlite.Connection,
    producto_sku: str,
    ubicacion_id: int,
) -> int:
    """Return the current stock for a product at a location.

    For Suelto this is the sum of movements; for regular shelves it is
    ``ubicaciones.stock_actual``.
    """
    es_suelto = await _is_suelto(db, ubicacion_id)
    return await _get_stock_anterior(db, producto_sku, ubicacion_id, es_suelto)


async def get_producto_stock_total(db: aiosqlite.Connection, producto_sku: str) -> int:
    """Return the total stock of a product across ALL ubicaciones.

    For regular shelves: SUM(ubicaciones.stock_actual) WHERE producto_id = sku.
    For Suelto: SUM(movimientos.cantidad) WHERE producto_id = sku AND estante is Suelto.
    Combined = regular_sum + suelto_sum.
    """
    regular = await _fetch_one_row(
        db,
        "SELECT COALESCE(SUM(stock_actual), 0) AS total FROM ubicaciones WHERE producto_id = ?",
        (producto_sku,),
    )
    regular_stock = int(regular["total"]) if regular else 0

    suelto = await _fetch_one_row(
        db,
        """
        SELECT COALESCE(SUM(m.cantidad), 0) AS total
        FROM movimientos m
        JOIN ubicaciones u ON u.id = m.ubicacion_id
        JOIN estantes e ON e.id = u.estante_id
        WHERE m.producto_id = ? AND e.nombre = 'Suelto'
        """,
        (producto_sku,),
    )
    suelto_stock = int(suelto["total"]) if suelto else 0

    return regular_stock + suelto_stock


async def get_producto_ubicaciones(
    db: aiosqlite.Connection,
    producto_sku: str,
    deposito_ids: Optional[list[int]] = None,
) -> list[dict]:
    """Return every ubicacion where ``producto_sku`` has stock, permission-filtered.

    Combines two sources into a single list:
      1. Regular shelves: ``ubicaciones.producto_id = sku`` with ``stock = stock_actual``.
      2. Suelto: SUM of ``movimientos.cantidad`` for the product across Suelto
         ubicaciones (one Suelto row per deposito's Suelto estante with non-zero stock).

    Permission filtering mirrors ``list_movimientos``:
      - ``deposito_ids is None``  (admin): no filter, all depositos returned.
      - ``deposito_ids is []``    (non-admin, no access): returns ``[]`` immediately.
      - ``deposito_ids is [a,b]`` (non-admin, restricted): ``WHERE d.id IN (a, b)``.

    The caller (endpoint) computes ``stock_total`` as the sum of per-row ``stock``
    so the total matches the permission-filtered view, not the global stock.
    """
    # Empty permission list → no results (matches list_movimientos contract).
    if deposito_ids is not None and not deposito_ids:
        return []

    # 1. Regular shelves — stock comes from ubicaciones.stock_actual.
    regular_sql = """
        SELECT
            u.id AS ubicacion_id,
            e.nombre AS estante_nombre,
            u.qr_valor,
            u.fila,
            u.columna,
            u.stock_actual AS stock,
            d.id AS deposito_id,
            d.nombre AS deposito_nombre,
            e.filas AS estante_filas,
            e.columnas AS estante_columnas,
            e.fila_order,
            e.columna_order,
            e.fila_format,
            e.columna_format,
            'regular' AS source
        FROM ubicaciones u
        JOIN estantes e ON e.id = u.estante_id
        JOIN depositos d ON d.id = e.deposito_id
        WHERE u.producto_id = ?
          AND u.estado = 'activo'
          AND e.deleted_at IS NULL
    """
    regular_params: list = [producto_sku]
    if deposito_ids is not None:
        placeholders = ",".join("?" for _ in deposito_ids)
        regular_sql += f" AND d.id IN ({placeholders})"
        regular_params.extend(deposito_ids)

    regular_rows: list[dict] = []
    async with db.execute(regular_sql, tuple(regular_params)) as cursor:
        rows = await cursor.fetchall()
        regular_rows = [dict(row) for row in rows]

    # 2. Suelto — stock is the SUM of movimientos.cantidad for that product.
    # One row per Suelto estante (typically one per deposito) with non-zero stock.
    suelto_sql = """
        SELECT
            u.id AS ubicacion_id,
            e.nombre AS estante_nombre,
            u.qr_valor,
            u.fila,
            u.columna,
            COALESCE(SUM(m.cantidad), 0) AS stock,
            d.id AS deposito_id,
            d.nombre AS deposito_nombre,
            e.filas AS estante_filas,
            e.columnas AS estante_columnas,
            e.fila_order,
            e.columna_order,
            e.fila_format,
            e.columna_format,
            'suelto' AS source
        FROM estantes e
        JOIN depositos d ON d.id = e.deposito_id
        JOIN ubicaciones u ON u.estante_id = e.id
        LEFT JOIN movimientos m ON m.ubicacion_id = u.id AND m.producto_id = ?
        WHERE e.nombre = 'Suelto'
          AND e.deleted_at IS NULL
          AND u.estado = 'activo'
    """
    suelto_params: list = [producto_sku]
    if deposito_ids is not None:
        placeholders = ",".join("?" for _ in deposito_ids)
        suelto_sql += f" AND d.id IN ({placeholders})"
        suelto_params.extend(deposito_ids)

    suelto_sql += (
        " GROUP BY u.id, e.nombre, u.qr_valor, u.fila, u.columna, d.id, d.nombre"
        " HAVING stock != 0"
    )

    suelto_rows: list[dict] = []
    async with db.execute(suelto_sql, tuple(suelto_params)) as cursor:
        rows = await cursor.fetchall()
        suelto_rows = [dict(row) for row in rows]

    # 3. Sin-ubicacion bucket — one synthetic row per ``stock_sin_ubicacion``
    # row for this product (R1 invariant: a row in the bucket table ALWAYS
    # means "there is bucket stock for this product", so no extra
    # ``cantidad > 0`` filter is needed — kept defensively in case a future
    # writer bypasses ``stock_sin_ubicacion_repository.drain``'s R1 cleanup).
    # ``ubicacion_id`` and ``qr_valor`` are NULL so the frontend can
    # discriminate the bucket row from a physical ubicacion via the
    # ``item.ubicacion_id === null`` predicate (REQ-C-004..006).
    #
    # No deposito filtering: the bucket is a per-PRODUCT concept (one row per
    # ``producto_id``, no per-deposito breakdown), so any user who can see the
    # product sees its bucket qty regardless of deposito permissions.
    # Branch order: physical (regular + Suelto) first, sin-ubicacion last
    # (design §3 + R5 — FE renders physical locations before the synthetic
    # bucket row).
    bucket_sql = """
        SELECT
            NULL AS ubicacion_id,
            'SIN UBICACION' AS estante_nombre,
            NULL AS qr_valor,
            0 AS fila,
            0 AS columna,
            s.cantidad AS stock,
            NULL AS deposito_id,
            '' AS deposito_nombre,
            NULL AS estante_filas,
            NULL AS estante_columnas,
            NULL AS fila_order,
            NULL AS columna_order,
            NULL AS fila_format,
            NULL AS columna_format,
            'sin-ubicacion' AS source
        FROM stock_sin_ubicacion s
        WHERE s.producto_id = ?
          AND s.cantidad > 0
    """
    bucket_params: list = [producto_sku]

    bucket_rows: list[dict] = []
    async with db.execute(bucket_sql, tuple(bucket_params)) as cursor:
        rows = await cursor.fetchall()
        bucket_rows = [dict(row) for row in rows]

    return regular_rows + suelto_rows + bucket_rows


async def list_movimientos(
    db: aiosqlite.Connection,
    filters: dict,
    deposito_ids: Optional[list[int]] = None,
) -> tuple[list[dict], int]:
    """Return filtered movements ordered by timestamp DESC plus total count.

    Supported filters: usuario_id, producto_sku, ubicacion_id, from_date, to_date.
    Pagination: limit, offset.

    When deposito_ids is a non-empty list, only movements whose ubicacion belongs
    to one of those depositos are returned. An empty list returns no results.
    Admins pass deposito_ids=None to bypass the filter.
    """
    if deposito_ids is not None and not deposito_ids:
        return [], 0

    where_clauses: list[str] = []
    params: list = []

    if filters.get("usuario_id") is not None:
        where_clauses.append("m.usuario_id = ?")
        params.append(filters["usuario_id"])

    if filters.get("producto_sku") is not None:
        where_clauses.append("m.producto_id = ?")
        params.append(filters["producto_sku"])

    if filters.get("ubicacion_id") is not None:
        where_clauses.append("m.ubicacion_id = ?")
        params.append(filters["ubicacion_id"])

    if filters.get("from_date") is not None:
        where_clauses.append("m.timestamp >= ?")
        params.append(filters["from_date"])

    if filters.get("to_date") is not None:
        where_clauses.append("m.timestamp <= ?")
        params.append(filters["to_date"])

    if deposito_ids is not None:
        placeholders = ",".join("?" for _ in deposito_ids)
        where_clauses.append(f"e.deposito_id IN ({placeholders})")
        params.extend(deposito_ids)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    count_sql = f"""
        SELECT COUNT(*)
        FROM movimientos m
        JOIN ubicaciones ubi ON ubi.id = m.ubicacion_id
        JOIN estantes e ON e.id = ubi.estante_id
        WHERE {where_sql}
    """
    async with db.execute(count_sql, tuple(params)) as cursor:
        total_row = await cursor.fetchone()
        total = total_row[0] if total_row else 0

    limit = max(1, min(int(filters.get("limit", 50)), 500))
    offset = max(0, int(filters.get("offset", 0)))

    query_sql = f"""
        SELECT
            m.id,
            m.usuario_id,
            u.nombre AS usuario_nombre,
            m.producto_id AS producto_sku,
            p.descripcion AS producto_descripcion,
            m.ubicacion_id,
            ubi.qr_valor AS ubicacion_qr,
            e.nombre AS estante_nombre,
            e.deposito_id,
            ubi.fila,
            ubi.columna,
            e.filas AS estante_filas,
            e.columnas AS estante_columnas,
            e.fila_order,
            e.columna_order,
            e.fila_format,
            e.columna_format,
            m.cantidad,
            m.stock_anterior,
            m.stock_nuevo,
            m.stock_general_anterior,
            m.stock_general_nuevo,
            m.timestamp,
            m.tipo
        FROM movimientos m
        LEFT JOIN usuarios u ON u.id = m.usuario_id
        LEFT JOIN productos p ON p.sku = m.producto_id
        JOIN ubicaciones ubi ON ubi.id = m.ubicacion_id
        JOIN estantes e ON e.id = ubi.estante_id
        WHERE {where_sql}
        ORDER BY m.timestamp DESC, m.id ASC
        LIMIT ? OFFSET ?
    """
    async with db.execute(query_sql, tuple(params) + (limit, offset)) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total


async def export_movimientos_csv(
    db: aiosqlite.Connection,
    filters: dict,
    deposito_ids: Optional[list[int]] = None,
) -> str:
    """Return a CSV string of all matching movements (no pagination)."""
    if deposito_ids is not None and not deposito_ids:
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow([
            "id",
            "usuario",
            "producto_sku",
            "producto_descripcion",
            "estante",
            "fila",
            "columna",
            "cantidad",
            "stock_anterior",
            "stock_nuevo",
            "fecha_hora",
            "tipo",
        ])
        return output.getvalue()

    where_clauses: list[str] = []
    params: list = []

    if filters.get("usuario_id") is not None:
        where_clauses.append("m.usuario_id = ?")
        params.append(filters["usuario_id"])

    if filters.get("producto_sku") is not None:
        where_clauses.append("m.producto_id = ?")
        params.append(filters["producto_sku"])

    if filters.get("ubicacion_id") is not None:
        where_clauses.append("m.ubicacion_id = ?")
        params.append(filters["ubicacion_id"])

    if filters.get("from_date") is not None:
        where_clauses.append("m.timestamp >= ?")
        params.append(filters["from_date"])

    if filters.get("to_date") is not None:
        where_clauses.append("m.timestamp <= ?")
        params.append(filters["to_date"])

    if deposito_ids is not None:
        placeholders = ",".join("?" for _ in deposito_ids)
        where_clauses.append(f"e.deposito_id IN ({placeholders})")
        params.extend(deposito_ids)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    query_sql = f"""
        SELECT
            m.id,
            u.nombre AS usuario,
            m.producto_id AS producto_sku,
            p.descripcion AS producto_descripcion,
            e.nombre AS estante,
            ubi.fila,
            ubi.columna,
            m.cantidad,
            m.stock_anterior,
            m.stock_nuevo,
            m.stock_general_anterior,
            m.stock_general_nuevo,
            m.timestamp AS fecha_hora,
            m.tipo
        FROM movimientos m
        LEFT JOIN usuarios u ON u.id = m.usuario_id
        LEFT JOIN productos p ON p.sku = m.producto_id
        JOIN ubicaciones ubi ON ubi.id = m.ubicacion_id
        JOIN estantes e ON e.id = ubi.estante_id
        WHERE {where_sql}
        ORDER BY m.timestamp DESC, m.id ASC
    """

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([
        "id",
        "usuario",
        "producto_sku",
        "producto_descripcion",
        "estante",
        "fila",
        "columna",
        "cantidad",
        "stock_anterior",
        "stock_nuevo",
        "fecha_hora",
        "tipo",
    ])

    async with db.execute(query_sql, tuple(params)) as cursor:
        rows = await cursor.fetchall()
        for row in rows:
            writer.writerow([
                row["id"],
                row["usuario"],
                row["producto_sku"],
                row["producto_descripcion"],
                row["estante"],
                row["fila"],
                row["columna"],
                row["cantidad"],
                row["stock_anterior"],
                row["stock_nuevo"],
                row["fecha_hora"],
                row["tipo"],
            ])

    return output.getvalue()


# ---------------------------------------------------------------------------
# Slice 2a additions (Part B phase 1)
# ---------------------------------------------------------------------------
# Pure data-layer helpers for the two new ``movimientos.tipo`` literals
# introduced by migration 016. Neither helper opens or commits a transaction —
# the caller (the surgery in ``ubicacion_repository`` for
# ``rescate_sin_ubicacion`` on Slice 2b, the ``backfill_orphans.py`` script
# for ``salvage_cleanup`` on Slice 4, or a unit test) wraps the call inside a
# single ``BEGIN IMMEDIATE`` / ``commit`` envelope per design R3.
#
# IMPORTANT ORDERING NOTE (for Slice 2b's surgery): call
# :func:`create_movimiento_rescate_sin_ubicacion` BEFORE mutating
# ``ubicaciones.stock_actual`` for the rescue (i.e. as the FIRST write in the
# assign-tx after the bucket drain, BEFORE the ubicacion UPDATE). This matches
# the existing convention in :func:`_create_movimiento_once` (which snapshots
# ``stock_general_anterior`` via :func:`get_producto_stock_total` BEFORE any
# ubicacion mutation — see lines 145-149) so the lazy stock_general snapshot
# taken here reflects the pre-mutation stock_general state.
#
# Spec anchors: REQ-B-006 (rescate), REQ-D-002 + REQ-D-003 (salvage),
# REQ-B-007, REQ-X-006.


async def create_movimiento_rescate_sin_ubicacion(
    db: aiosqlite.Connection,
    producto_id: str,
    ubicacion_id: int,
    qty: int,
    usuario_id: Optional[int] = None,
) -> int:
    """Record a ``rescate_sin_ubicacion`` movimiento: ``qty`` units rescued
    FROM the sin-ubicacion bucket INTO ``ubicacion_id``.

    Called from the assign-surgery (Slice 2b) when an assign flow drains > 0
    units from :mod:`stock_sin_ubicacion_repository` into the assigned
    location. The audit record captures the rescue as a separate movement so
    the eventual Suelto policy is unchanged and the bucket-out movement is
    traceable per-ubicacion.

    Stock-general snapshots are computed lazily via
    :func:`get_producto_stock_total`: the bucket is NOT counted in
    stock_general (per the 3-stock concept documented at the top of
    :mod:`stock_sin_ubicacion_repository`), so moving ``qty`` units OUT of the
    bucket INTO a ubicacion INCREASES stock_general by exactly ``qty``:

      * ``stock_general_anterior`` = product's current total stock
        (SUM(ubicaciones.stock_actual) + Suelto movimiento sums). Caller must
        call this helper BEFORE updating ``ubicaciones.stock_actual`` for the
        rescue so the snapshot reflects the pre-mutation state.
      * ``stock_general_nuevo``    = ``stock_general_anterior + qty``.

    Per-ubicacion snapshots:
      * ``stock_anterior`` = 0 (the assigned location's prior quantity is
        captured by the matching ``asignacion`` / ``alta`` movimiento; this
        row records the per-ubicacion rescue event as a 0 -> qty delta for
        audit clarity).
      * ``stock_nuevo``    = qty (the rescued units now reside at this
        ubicacion).

    ``usuario_id`` is nullable per migration 012, allowing callers without a
    session (e.g. backfill-style batch scripts) to record audit rows.

    Caller wraps in a ``BEGIN IMMEDIATE`` / ``commit`` envelope (design R3).
    This function does NOT commit.

    Args:
        db: Configured aiosqlite connection inside an active transaction.
        producto_id: SKU of the product whose bucket units are being rescued.
        ubicacion_id: ID of the ubicacion receiving the rescued units.
        qty: Units moved from bucket -> ubicacion (> 0; rescue rows with
            qty == 0 are never written — the caller guards on ``drained > 0``
            per task 2b.2).
        usuario_id: Optional user id for audit attribution (NULL allowed).

    Returns:
        The new ``movimientos.id``.
    """
    stock_general_anterior = await get_producto_stock_total(db, producto_id)
    stock_general_nuevo = stock_general_anterior + qty
    cursor = await db.execute(
        """
        INSERT INTO movimientos (
            usuario_id, producto_id, ubicacion_id, cantidad,
            stock_anterior, stock_nuevo, tipo,
            stock_general_anterior, stock_general_nuevo
        )
        VALUES (?, ?, ?, ?, ?, ?, 'rescate_sin_ubicacion', ?, ?)
        """,
        (
            usuario_id,
            producto_id,
            ubicacion_id,
            qty,
            0,
            qty,
            stock_general_anterior,
            stock_general_nuevo,
        ),
    )
    return cursor.lastrowid


async def create_movimiento_salvage_cleanup(
    db: aiosqlite.Connection,
    ubicacion_id: int,
    qty: int,
    usuario_id: Optional[int] = None,
) -> int:
    """Record a ``salvage_cleanup`` movimiento for ``qty`` orphan units at
    ``ubicacion_id`` (``producto_id`` is intentionally NULL — see REQ-D-002).

    Called by the one-shot ``backfill_orphans.py`` script (Slice 4) for each
    orphan ubicacion (``ubicaciones.stock_actual > 0 AND producto_id IS
    NULL``). The script zeroes ``ubicaciones.stock_actual`` in the same
    ``BEGIN IMMEDIATE`` / ``commit`` envelope, so per-ubicacion snapshots on
    this movimiento row describe the cleanup:

      * ``stock_anterior`` = qty (the orphan ubicacion's prior
        ``stock_actual``).
      * ``stock_nuevo``    = 0 (the ubicacion is zeroed in the same tx).

    Because the orphan has NO product (by definition), the
    ``stock_general_anterior`` and ``stock_general_nuevo`` columns cannot be
    computed from existing data — they are recorded as 0 / 0 (the orphan's
    stock contributes nothing to any product's ``stock_general``, since no
    product is linked to it).

    The FK on ``movimientos.producto_id`` to ``productos(sku)`` accepts NULL
    (per migration 001:82 — ``producto_id TEXT`` has no NOT NULL). SQLite's
    CHECK on ``movimientos.tipo`` accepts ``'salvage_cleanup'`` ONLY after
    migration 016 (this slice).

    ``usuario_id`` is nullable per migration 012, allowing backfill scripts
    without a user session to record audit rows.

    Caller wraps in a ``BEGIN IMMEDIATE`` / ``commit`` envelope (design R3).
    This function does NOT commit.

    Args:
        db: Configured aiosqlite connection inside an active transaction.
        ubicacion_id: ID of the orphan ubicacion being cleaned up.
        qty: Units being salvaged (must equal the ubicacion's stock_actual at
            call time; the caller is expected to zero it in the same tx).
        usuario_id: Optional user id for audit attribution (NULL allowed —
            backfill typically has no live user session).

    Returns:
        The new ``movimientos.id``.
    """
    cursor = await db.execute(
        """
        INSERT INTO movimientos (
            usuario_id, producto_id, ubicacion_id, cantidad,
            stock_anterior, stock_nuevo, tipo,
            stock_general_anterior, stock_general_nuevo
        )
        VALUES (?, NULL, ?, ?, ?, 0, 'salvage_cleanup', 0, 0)
        """,
        (usuario_id, ubicacion_id, qty, qty),
    )
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Slice 2b additions (Part B phase 2 — explicit-snapshot helpers)
# ---------------------------------------------------------------------------
# Two more data-layer helpers added by Slice 2b. Both take EXPLICIT
# ``stock_general_anterior`` / ``stock_general_nuevo`` snapshots computed by
# the caller (the surgery in ``ubicacion_repository`` for the explicit unassign
# and assign flows). Using explicit snapshots rather than the lazy
# ``get_producto_stock_total`` call from inside the helper (as the rescue and
# salvage helpers do) gives the caller exact control over what the audit row
# records for each side of the movement — important when the caller performs
# multiple writes in one ``BEGIN IMMEDIATE`` transaction (the ubicacion UPDATE,
# the bucket UPSERT / drain, AND the movimiento INSERT) and the lazy read would
# land at the wrong mid-tx moment.
#
# Neither helper opens or commits a transaction — the caller wraps both in the
# single ``BEGIN IMMEDIATE`` / ``commit`` envelope per design R3.
#
# Spec anchors: REQ-B-003 (desasignacion audit-fix), REQ-B-008 (asignacion
# remainder), REQ-X-006.


async def create_movimiento_desasignacion(
    db: aiosqlite.Connection,
    producto_id: str,
    ubicacion_id: int,
    stock_anterior: int,
    stock_general_anterior: int,
    stock_general_nuevo: int,
    usuario_id: Optional[int] = None,
) -> int:
    """Record a ``desasignacion`` movimiento with EXPLICIT stock-general
    snapshots for the OUTGOING product (Slice 2b audit-fix path — REQ-B-003).

    Called by :func:`ubicacion_repository.unassign_producto_from_ubicacion`
    AFTER it has: (1) snapshotted the OUTGOING product's stock_general with
    :func:`get_producto_stock_total`, (2) UPSERTed the freed qty into the
    ``stock_sin_ubicacion`` bucket, and (3) zeroed ``ubicaciones.stock_actual``
    + NULLed ``ubicaciones.producto_id`` for the freed cell — all inside the
    same ``BEGIN IMMEDIATE`` / ``commit`` envelope.

    Snapshot contract (REQ-B-003 + scenario B5):
      * ``stock_general_anterior`` MUST be the OUTGOING product's
        stock_general computed BEFORE the unassign mutation (``stock_general
        = SUM(ubicaciones.stock_actual WHERE producto_id = OUTGOING) +
        Suelto_sums``).
      * ``stock_general_nuevo``   MUST reflect the OUTGOING product's
        stock_general AFTER the unassign (``anterior - stock_anterior``,
        because the freed qty moved INTO the bucket which is NOT counted in
        stock_general per the 3-stock concept).

    Per-row values (matches the historical ``desasignacion`` audit shape):
      * ``cantidad = 0`` (this row records the UN-TAG event — no qty delta per
        the row itself; the qty that left the ubicacion is captured by
        ``stock_anterior`` below).
      * ``stock_anterior`` = the ubicacion's prior ``stock_actual`` (caller-
        supplied; = the qty now sitting in the bucket).
      * ``stock_nuevo    = 0`` (REQ-B-001 zeroed the ubicacion).

    ``usuario_id`` is nullable per migration 012.

    Caller wraps in a ``BEGIN IMMEDIATE`` / ``commit`` envelope (design R3).
    This function does NOT commit.

    Args:
        db: Configured aiosqlite connection inside an active transaction.
        producto_id: SKU of the OUTGOING product being unassigned.
        ubicacion_id: ID of the real freed ubicacion (NOT NULL — REQ-B-004).
        stock_anterior: The ubicacion's prior ``stock_actual`` (= qty moved to
            the bucket by the caller).
        stock_general_anterior: OUTGOING product's stock_general BEFORE
            unassign (caller's snapshot — REQ-B-003).
        stock_general_nuevo: OUTGOING product's stock_general AFTER unassign
            (= ``anterior - stock_anterior``).
        usuario_id: Optional user id for audit attribution (NULL allowed).

    Returns:
        The new ``movimientos.id``.
    """
    cursor = await db.execute(
        """
        INSERT INTO movimientos (
            usuario_id, producto_id, ubicacion_id, cantidad,
            stock_anterior, stock_nuevo, tipo,
            stock_general_anterior, stock_general_nuevo
        )
        VALUES (?, ?, ?, 0, ?, 0, 'desasignacion', ?, ?)
        """,
        (
            usuario_id,
            producto_id,
            ubicacion_id,
            stock_anterior,
            stock_general_anterior,
            stock_general_nuevo,
        ),
    )
    return cursor.lastrowid


async def create_movimiento_asignacion(
    db: aiosqlite.Connection,
    producto_id: str,
    ubicacion_id: int,
    qty: int,
    stock_general_anterior: int,
    stock_general_nuevo: int,
    usuario_id: Optional[int] = None,
) -> int:
    """Record an ``asignacion`` movimiento for ``qty`` newly-counted units
    with EXPLICIT stock-general snapshots (Slice 2b — REQ-B-008).

    Called by :func:`ubicacion_repository.assign_producto_to_ubicacion` when
    the user has entered a non-zero qty at the ubicacion AND the bucket was
    not enough to cover it (``remainder > 0``). The caller computes:

      * ``qty``                       = ``remainder = max(0, entered_qty - bucket)``.
      * ``stock_general_anterior``    = stock_general AFTER the bucket-rescue
        drained into the ubicacion but BEFORE the remainder qty takes
        residence (``pre_assign_stock_general + drain_amount``).
      * ``stock_general_nuevo``       = stock_general AFTER the remainder qty
        takes residence (``anterior + remainder`` = ``pre_assign_stock_general
        + entered_qty``).

    The caller is responsible for ordering: it MUST call
    :func:`create_movimiento_rescate_sin_ubicacion` (if ``drain_amount > 0``)
    BEFORE calling this helper for the same product, so the rescue's lazy
    snapshot captures the pre-rescue state. This helper then receives the
    post-rescue ``anterior`` explicitly from the caller (the rescue helper's
    lazy snapshot cannot be re-read after the rescue because ``get_producto_stock_total``
    returns the same value — bucket is not counted; only ``ubicaciones.stock_actual``
    counts, which the caller has not yet mutated).

    Per-row values:
      * ``cantidad = qty`` (the newly-counted units entering this cell —
        REQ-B-008: NO asignacion row is written when remainder = 0).
      * ``stock_anterior = 0`` (fresh count — the ubicacion's prior qty from
        this asignacion's perspective is 0; the rescue qty already captured
        by the matching ``rescate_sin_ubicacion`` row).
      * ``stock_nuevo    = qty``.

    ``usuario_id`` is nullable per migration 012.

    Caller wraps in a ``BEGIN IMMEDIATE`` / ``commit`` envelope (design R3).
    This function does NOT commit.

    Args:
        db: Configured aiosqlite connection inside an active transaction.
        producto_id: SKU of the product being newly counted at this cell.
        ubicacion_id: ID of the assigned ubicacion.
        qty: Newly-counted remainder qty (``remainder = max(0,
            entered_qty - bucket_qty)``; MUST be > 0 per REQ-B-008).
        stock_general_anterior: Product's stock_general AFTER the rescue
            drained into the ubicacion but BEFORE this remainder qty.
        stock_general_nuevo: Product's stock_general AFTER this remainder qty
        takes residence (= ``anterior + qty``).
        usuario_id: Optional user id for audit attribution (NULL allowed).

    Returns:
        The new ``movimientos.id``.
    """
    cursor = await db.execute(
        """
        INSERT INTO movimientos (
            usuario_id, producto_id, ubicacion_id, cantidad,
            stock_anterior, stock_nuevo, tipo,
            stock_general_anterior, stock_general_nuevo
        )
        VALUES (?, ?, ?, ?, 0, ?, 'asignacion', ?, ?)
        """,
        (
            usuario_id,
            producto_id,
            ubicacion_id,
            qty,
            qty,
            stock_general_anterior,
            stock_general_nuevo,
        ),
    )
    return cursor.lastrowid
