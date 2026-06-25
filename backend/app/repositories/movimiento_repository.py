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
                    stock_general_anterior, stock_general_anterior,
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
            m.cantidad,
            m.stock_anterior,
            m.stock_nuevo,
            m.stock_general_anterior,
            m.stock_general_nuevo,
            m.timestamp,
            m.tipo
        FROM movimientos m
        JOIN usuarios u ON u.id = m.usuario_id
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

    return {
        "stock_actual": stock,
        "is_assigned": is_assigned,
        "es_suelto": es_suelto,
        "existing_producto_sku": existing_producto_sku,
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
            m.cantidad,
            m.stock_anterior,
            m.stock_nuevo,
            m.stock_general_anterior,
            m.stock_general_nuevo,
            m.timestamp,
            m.tipo
        FROM movimientos m
        JOIN usuarios u ON u.id = m.usuario_id
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
        JOIN usuarios u ON u.id = m.usuario_id
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
