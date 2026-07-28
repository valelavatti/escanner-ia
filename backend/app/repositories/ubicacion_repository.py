"""Ubicacion (shelf cell) data access layer.

Each ubicacion belongs to an estante and represents a single physical cell.
QR values are generated adaptively based on the estante's dimensions so that
single-row, single-column, and single-cell shelves keep their QR labels short.
"""

from typing import Optional

import aiosqlite

from app.repositories import movimiento_repository as _mov_repo
from app.repositories import stock_sin_ubicacion_repository as _bucket_repo


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
    *,
    entered_qty: int = 0,
) -> bool:
    """Assign a product SKU to an empty ubicacion and drain the
    sin-ubicacion bucket FIRST (REQ-B-005, B-006, B-007, B-008, B-009,
    B-010, R3). Closes the B6 assign-overwrite edge case (Slice 6):
    re-using the existing ``unassign_producto_from_ubicacion`` flow when
    the cell is already occupied by a DIFFERENT product.

    Drain semantics (one ``BEGIN IMMEDIATE`` / ``commit`` atomic transaction
    per design R3):

      1. Load the ubicacion row → current ``producto_id`` and stock_actual
         (typically 0 for a freshly-tagged empty cell, or — for the B6
         edge case — the previous occupant's leftover qty).
      2. If the ubicacion does not exist → ``False``.
      3. If the ubicacion already holds a DIFFERENT product (B6 edge case):
         FIRST call ``unassign_producto_from_ubicacion(ubicacion_id)`` so
         the previous product's leftover stock is moved into ITS bucket
         with a proper ``desasignacion`` audit row (instead of silently
         reattributing the previous occupant's units to the new product).
         Then re-read the now-empty cell and continue the assign flow.
      4. If the ubicacion already holds the SAME product → raise
         ``UbicacionOcupadaError`` (preserves the historical tag-only guard
         so the FE admin modal can detect "nothing to do" at the cell).
      5. Compute:
           ``drain_amount = min(bucket_qty, entered_qty)``
           ``remainder    = max(0, entered_qty - bucket_qty)``
      6. Inside ONE tx:
         (a) If ``drain_amount > 0``: call
             ``stock_sin_ubicacion_repository.drain(...)`` (R1 deletes the
             row when cantidad reaches 0 — no zero-orphans).
         (b) If ``drain_amount > 0``: call
             ``movimiento_repository.create_movimiento_rescate_sin_ubicacion(...)``
             BEFORE mutating ``ubicaciones.stock_actual`` — CRITICAL ORDERING
             CONTRACT (the rescue helper lazily snapshots
             ``stock_general_anterior`` via ``get_producto_stock_total``;
             if the ubicacion were mutated first, the snapshot would land in
             the post-mutation state — see the carry-forward from Slice 2a).
         (c) UPDATE the ubicacion:
             ``producto_id = producto_id``,
             ``stock_actual = current_stock + drain_amount + remainder``
             (additive — after the B6 path ``current_stock`` is 0 because
             the unassign step zeroed the cell; in the fresh-cell path it
             is typically 0 anyway, but additive-on-0 is identity).
         (d) If ``remainder > 0``: call
             ``movimiento_repository.create_movimiento_asignacion(...)`` with
             EXPLICIT snapshots (anterior = pre + drain; nuevo = pre + drain
             + remainder = pre + entered_qty). NO ``asignacion`` row is
             written when ``remainder == 0`` (REQ-B-008).

    ``entered_qty`` is keyword-only (PEP 3102) with default ``0`` for
    backward compat with the existing router caller at
    ``app.api.v1.endpoints.ubicaciones.py`` which does NOT pass a qty (the
    FE admin modal tags the ubicacion without entering a count). The bucket
    drain only happens when an explicit qty is supplied; the router call
    therefore keeps its historical "tag only" semantics modulo the audit
    row — moving forward, a tag-only assign writes NO ``asignacion`` row
    (per REQ-B-008, no row when remainder = 0).

    Raises:
        UbicacionOcupadaError: if the ubicacion already has the SAME product
            assigned (the historical tag-only guard — no rewrite needed).
    """
    async with db.execute(
        "SELECT producto_id, stock_actual FROM ubicaciones WHERE id = ?",
        (ubicacion_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return False

    previous_producto_id = row["producto_id"]

    # B6 edge case (Slice 6 — assign-overwrite): if the cell currently
    # holds a DIFFERENT product with possibly non-zero leftover stock,
    # delegate the "previous occupant cleanup" to the existing
    # ``unassign_producto_from_ubicacion`` surgery (the Slice 2b flow
    # that moves its qty into ITS bucket with a proper ``desasignacion``
    # audit row) BEFORE assigning the new product. This reuses the audit +
    # bucket mechanism verbatim instead of silently overwriting the cell
    # and leaving the previous occupant's stock rotted in place (or, worse,
    # treating it as the new product's stock).
    if previous_producto_id is not None and previous_producto_id != producto_id:
        await unassign_producto_from_ubicacion(
            db, ubicacion_id=ubicacion_id, usuario_id=usuario_id
        )
        # The unassign committed its own tx and zeroed the cell (REQ-B-001).
        # Re-read so the remainder of this assign flow operates on FRESH
        # state (producto_id=NULL, stock_actual=0) — the local ``row``
        # captured above now holds STALE pre-unassign values.
        async with db.execute(
            "SELECT producto_id, stock_actual FROM ubicaciones WHERE id = ?",
            (ubicacion_id,),
        ) as cursor:
            row = await cursor.fetchone()
        current_stock_actual = row["stock_actual"]
    elif previous_producto_id is not None:
        # Same product already at this cell — preserve the historical
        # tag-only guard so the FE admin modal can detect "no rewrite
        # needed" (the object already holds this product); a tag-only call
        # through ``assign_producto_to_ubicacion`` should not silently
        # re-zero or re-sum the cell.
        raise UbicacionOcupadaError("La ubicacion ya tiene un producto asignado")
    else:
        current_stock_actual = row["stock_actual"]

    # Snapshot the product's stock_general BEFORE any mutation. The rescue
    # helper will call ``get_producto_stock_total`` lazily inside the tx and
    # get this exact same value (bucket is NOT counted in stock_general per
    # the 3-stock concept, and the ubicaciones row has not been mutated yet).
    # Captured once here so the explicit snapshots for the asignacion
    # remainder row (step d) are deterministic without re-reading the lazy
    # snapshot between the rescue and asignacion writes.
    pre_assign_stock_general = await _mov_repo.get_producto_stock_total(
        db, producto_id
    )

    bucket_qty = await _bucket_repo.get_cantidad(db, producto_id)
    drain_amount = min(bucket_qty, entered_qty)
    remainder = max(0, entered_qty - bucket_qty)

    await db.execute("BEGIN IMMEDIATE")
    try:
        # (a) Drain the bucket FIRST. R1 deletes the row when cantidad
        # reaches 0. The drain must happen BEFORE the rescue helper so the
        # rescue's lazy ``get_producto_stock_total`` snapshot still sees the
        # pre-rescue state — but the bucket is NOT counted in stock_general
        # anyway, so the snapshot value would be the same before/after the
        # drain. The ordering matters in step (b): the rescue helper MUST run
        # BEFORE the ubicacion UPDATE.
        if drain_amount > 0:
            await _bucket_repo.drain(db, producto_id, drain_amount)

        # (b) Rescue movimiento — MUST be called BEFORE mutating
        # ``ubicaciones.stock_actual`` (carry-forward #1 from Slice 2a). The
        # helper lazily snapshots ``stock_general_anterior`` and we want it
        # to capture the pre-mutation state.
        if drain_amount > 0:
            await _mov_repo.create_movimiento_rescate_sin_ubicacion(
                db,
                producto_id=producto_id,
                ubicacion_id=ubicacion_id,
                qty=drain_amount,
                usuario_id=usuario_id,
            )

        # (c) UPDATE the ubicacion: tag the product, set the new stock_actual
        # = old + drain + remainder (= old + entered_qty when remainder =
        # entered_qty - drain). The drain qty (rescued from bucket) AND the
        # remainder (newly counted) both take physical residence at the cell.
        new_stock_actual = current_stock_actual + drain_amount + remainder
        await db.execute(
            """
            UPDATE ubicaciones
            SET producto_id = ?,
                stock_actual = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (producto_id, new_stock_actual, ubicacion_id),
        )

        # (d) Asignacion movimiento for the REMAINDER (newly-counted qty).
        # REQ-B-008: NO asignacion row is written when remainder = 0.
        # Explicit snapshots so the helper does NOT re-read stock_general
        # (it would see the post-UPDATE state — wrong for the audit row's
        # ``anterior``). anterior captures the state AFTER the rescue
        # drained into the cell but BEFORE the remainder qty takes residence
        # (= pre + drain); nuevo is the post-tx total (= pre + entered_qty).
        if remainder > 0:
            stock_general_anterior_asignacion = (
                pre_assign_stock_general + drain_amount
            )
            stock_general_nuevo_asignacion = (
                pre_assign_stock_general + drain_amount + remainder
            )
            await _mov_repo.create_movimiento_asignacion(
                db,
                producto_id=producto_id,
                ubicacion_id=ubicacion_id,
                qty=remainder,
                stock_general_anterior=stock_general_anterior_asignacion,
                stock_general_nuevo=stock_general_nuevo_asignacion,
                usuario_id=usuario_id,
            )

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return True


async def unassign_producto_from_ubicacion(
    db: aiosqlite.Connection,
    ubicacion_id: int,
    usuario_id: int,
) -> bool:
    """Unassign the product from a ubicacion (REQ-B-001, B-002, B-003,
    B-004, B-009, R3).

    Replaces the historical "soft-clear" behavior (which left stock_actual
    untouched and snapshotted the OLD product's stock_general AFTER the
    producto_id=NULL UPDATE) with a real relocation:

      1. Load the ubicacion row → get the OUTGOING ``producto_id`` and the
         qty sitting at the cell (its ``stock_actual``).
      2. If the ubicacion does not exist → ``False``.
      3. If the ubicacion has no product assigned (``producto_id IS NULL``)
         → no-op, return ``True`` (nothing to unassign).
      4. Snapshot the OUTGOING product's stock_general BEFORE any mutation
         (REQ-B-003 audit-fix + scenario B5 — the OLD product's snapshot,
         NOT some NEW product's).
      5. Inside ONE ``BEGIN IMMEDIATE`` / ``commit`` transaction:
         (a) UPSERT the freed qty into the ``stock_sin_ubicacion`` bucket
             via ``stock_sin_ubicacion_repository.upsert_add(...)`` — moves
             qty into the bucket (REQ-B-002; qty == 0 is a no-op per R1,
             no zero-row is ever created).
         (b) UPDATE ``ubicaciones`` → ``producto_id = NULL,
             stock_actual = 0`` (REQ-B-001 zero; the qty that was sitting
             at the cell has just been moved to the bucket in (a) — both
             writes in the same atomic tx).
         (c) Write a ``desasignacion`` movimiento row via
             ``movimiento_repository.create_movimiento_desasignacion(...)``
             with the OUTGOING product's stock_general snapshots computed in
             step 4 — the explicit audit-mis-attribution FIX (REQ-B-003 +
             scenario B5; ``ubicacion_id`` is the real freed ubicacion,
             NOT NULL — REQ-B-004).

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

    # No product to unassign → no-op. Spec: "If producto_id_actual IS NULL
    # → no-op (nothing to unassign). Return early." Return True (the ubicacion
    # existed; matching the historical pre-surgery return semantics).
    if old_producto_id is None:
        return True

    # Step 4 — Snapshot the OUTGOING product's stock_general BEFORE any
    # mutation (REQ-B-003 + scenario B5). Captured OUTSIDE the BEGIN
    # IMMEDIATE block so a busy writer lock does not encapsulate the
    # (cheap, readonly) snapshot; the value reflects
    # SUM(ubicaciones.stock_actual WHERE producto_id = OUTGOING) + Suelto
    # sums at the unassign moment, INCLUDING the qty at the target
    # ubicacion itself (because we have not yet zeroed the cell).
    stock_general_anterior = await _mov_repo.get_producto_stock_total(
        db, old_producto_id
    )
    # The bucket is NOT counted in stock_general (3-stock concept). Moving
    # qty from the ubicacion INTO the bucket therefore DECREASES the OLD
    # product's stock_general by exactly ``stock_anterior``.
    stock_general_nuevo = stock_general_anterior - stock_anterior

    # Step 5 — Atomic surgery: bucket UPSERT + ubicacion zero + audit row,
    # all in ONE ``BEGIN IMMEDIATE`` / ``commit`` tx (design R3).
    await db.execute("BEGIN IMMEDIATE")
    try:
        # (a) Move the freed qty into the bucket. R1 enforces DELETE-on-zero;
        # ``upsert_add`` with qty == 0 is a no-op (no zero-row is created).
        await _bucket_repo.upsert_add(db, old_producto_id, stock_anterior)

        # (b) Zero the cell + clear the product assignment (REQ-B-001 +
        # REQ-B-002). The qty has just been moved into the bucket in (a)
        # so the SQL-level invariant ``ubicaciones.stock_actual = 0`` for
        # the freed cell is consistent with the bucket gain of the same qty.
        await db.execute(
            """
            UPDATE ubicaciones
            SET producto_id = NULL,
                stock_actual = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (ubicacion_id,),
        )

        # (c) Audit row with EXPLICIT snapshots (the mis-attribution fix —
        # REQ-B-003). The helper takes the OLD product's pre-unassign
        # (anterior) and post-unassign (nuevo = anterior - qty)
        # stock_general verbatim from the caller; it does NOT re-read
        # lazily (which would now see the post-UPDATE state — the OLD
        # product's stock_general decremented by ``stock_anterior`` — and
        # record anterior == nuevo == post-state, defeating the audit row's
        # purpose).
        await _mov_repo.create_movimiento_desasignacion(
            db,
            producto_id=old_producto_id,
            ubicacion_id=ubicacion_id,
            stock_anterior=stock_anterior,
            stock_general_anterior=stock_general_anterior,
            stock_general_nuevo=stock_general_nuevo,
            usuario_id=usuario_id,
        )

        await db.commit()
    except Exception:
        await db.rollback()
        raise

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
