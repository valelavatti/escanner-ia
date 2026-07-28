"""stock_sin_ubicacion — the "sin-ubicacion bucket" data layer.

The scanner tracks THREE stock dimensions per product (REQ-X-001):

1. ``stock_general``
        The product's TOTAL stock across the warehouse. Computed on demand
        (no table): ``SUM(ubicaciones.stock_actual)`` for the product on
        regular shelves + ``SUM(movimientos.cantidad)`` for the product on
        Suelto shelves. See
        :func:`movimiento_repository.get_producto_stock_total`.

2. ``ubicaciones.stock_actual``
        PER-LOCATION stock; one row per physical cell. (Suelto is a real 1x1
        ubicacion with id=1, qr_valor='Suelto' — it belongs here, NOT in the
        bucket.)

3. ``stock_sin_ubicacion.cantidad``  — THE SIN UBICACION BUCKET
        Units that were UN-assigned from a cell (an admin cancels an
        assignment, or a cell is reassigned to a DIFFERENT product while still
        holding units of the original product). They have no physical home
        YET; they wait in the bucket until the next ``assign`` flow that
        re-targets the same product "rescues" them (see the
        ``rescate_sin_ubicacion`` movimiento tipo introduced by migration
        016).

The bucket is NEVER a row in ``ubicaciones`` (no sentinel QR, no overlap with
Suelto). Discrimination between a Suelto ubicacion and the sin-ubicacion
bucket happens at the QUERY layer, not the data layer: Suelto shows up via
its real ``ubicaciones`` row (ubicacion_id=1); the bucket shows up via a
synthetic UNION branch (ubicacion_id=NULL, label="SIN UBICACION"). Suelto is a
PHYSICAL storage modality (loose units in a bin); the bucket is a TRANSIT
state (bookkeeping for units that lost their physical cell).

R1 INVARIANT — DELETE-row-on-zero
--------------------------------
When ``stock_sin_ubicacion.cantidad`` reaches 0 (either via :func:`drain` or
via an explicit :func:`delete_if_zero`), the row is REMOVED. A row in this
table ALWAYS means "there IS bucket stock for this product". The presence
predicate ``EXISTS (SELECT 1 FROM stock_sin_ubicacion WHERE producto_id = ?)``
is the same as the ``cantidad > 0`` predicate. This keeps every consumer
(``get_producto_ubicaciones``, future admin views, the backfill script) free
of ``WHERE cantidad > 0`` filters.

TRANSACTION DISCIPLINE
----------------------
This repository performs ONLY data operations. It never opens or commits a
transaction — the caller (the surgery in ``ubicacion_repository`` for Slice
2b, the ``backfill_orphans.py`` script for Slice 4, or a test) wraps every
write in a ``BEGIN IMMEDIATE`` / ``commit`` envelope per design R3. This
matches the convention of the rest of the repository layer: helpers do data,
the orchestrating caller owns the transaction boundary.

All queries use parameterized ``?`` placeholders — no f-strings, no string
interpolation of user input (SQLite injection-safety per the SQLite skill).

Spec anchors: REQ-B-002, REQ-B-004, REQ-B-005, REQ-B-006, REQ-B-007,
REQ-C-001, REQ-X-001, R1.
"""

from __future__ import annotations

import aiosqlite


async def get_cantidad(db: aiosqlite.Connection, producto_id: str) -> int:
    """Return the bucket qty for ``producto_id`` (0 if no row).

    R1-invariant readers and absence-test helpers MUST call this function
    instead of raw SQL so the "no row == 0 units" convention is centralized
    here.
    """
    async with db.execute(
        "SELECT cantidad FROM stock_sin_ubicacion WHERE producto_id = ?",
        (producto_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return 0
        return int(row[0])


async def upsert_add(
    db: aiosqlite.Connection,
    producto_id: str,
    qty: int,
) -> int:
    """Add ``qty`` units to the bucket for ``producto_id`` (UPSERT) and return
    the new ``cantidad``.

    If no row exists, INSERT a fresh row with ``cantidad = qty``. If a row
    already exists, atomically add ``qty`` to its ``cantidad`` via the
    ``ON CONFLICT(producto_id) DO UPDATE`` clause. ``updated_at`` is bumped to
    ``CURRENT_TIMESTAMP`` on every write.

    ``qty == 0`` is a strict no-op: it does NOT INSERT a row (R1 — no zero-row
    orphans ever exist) and returns the current ``cantidad`` (0 if no row).

    R1 (DELETE-row-on-zero) does NOT fire here — :func:`upsert_add` only
    INCREASES ``cantidad`` (or inserts a fresh positive row); only
    :func:`drain` and :func:`delete_if_zero` ever remove rows. The CHECK
    constraint ``cantidad >= 0`` on the table guarantees a negative ``qty``
    cannot sneak through.
    """
    if qty < 0:
        raise ValueError("qty must be >= 0 for upsert_add")
    if qty == 0:
        # No-op: do NOT create a zero-row (R1 invariant). Just read the
        # current qty (0 if no row).
        return await get_cantidad(db, producto_id)
    await db.execute(
        """
        INSERT INTO stock_sin_ubicacion (producto_id, cantidad, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(producto_id) DO UPDATE SET
            cantidad = cantidad + excluded.cantidad,
            updated_at = CURRENT_TIMESTAMP
        """,
        (producto_id, qty),
    )
    # Re-read on the SAME connection so we see the just-written (uncommitted)
    # state — the caller is responsible for committing.
    return await get_cantidad(db, producto_id)


async def drain(
    db: aiosqlite.Connection,
    producto_id: str,
    requested_qty: int,
) -> int:
    """Drain up to ``requested_qty`` units from the bucket for ``producto_id``
    and return the actual drained amount.

    The drain is capped at available qty:

      * bucket holds ``>= requested_qty``: ``cantidad`` decreases by
        ``requested_qty``; drained == requested_qty.
      * bucket holds ``<  requested_qty``: ``cantidad`` goes to 0; drained ==
        bucket qty at call time.
      * bucket has no row (qty = 0 by R1): drained == 0, no row inserted.

    R1 (DELETE-row-on-zero): if the resulting ``cantidad`` is 0, the row is
    DELETED in this same call so no zero-row orphan persists. Returns the
    actual drained amount — always in ``[0, requested_qty]``.

    Caller wraps in a ``BEGIN IMMEDIATE`` / ``commit`` envelope (design R3).
    This function does NOT commit.
    """
    if requested_qty < 0:
        raise ValueError("requested_qty must be >= 0 for drain")

    current = await get_cantidad(db, producto_id)
    if current == 0:
        # No row to drain. R1 invariant: a missing row IS the zero state.
        return 0

    drained = min(current, requested_qty)
    new_qty = current - drained

    if new_qty == 0:
        # R1: delete the row when cantidad hits zero (no zero-row orphans).
        await db.execute(
            "DELETE FROM stock_sin_ubicacion WHERE producto_id = ?",
            (producto_id,),
        )
    else:
        await db.execute(
            """
            UPDATE stock_sin_ubicacion
            SET cantidad = ?, updated_at = CURRENT_TIMESTAMP
            WHERE producto_id = ?
            """,
            (new_qty, producto_id),
        )
    return drained


async def delete_if_zero(db: aiosqlite.Connection, producto_id: str) -> None:
    """Defensive: delete the bucket row for ``producto_id`` IF its
    ``cantidad`` is 0.

    Normally :func:`drain` already deletes the row when ``cantidad`` reaches 0
    (enforcing the R1 invariant). This helper exists as a safety net for
    callers that modify ``cantidad`` through other paths (or that simply want
    to assert the invariant holds after their own writes).

    NO-OP if no row exists, or if the existing row's ``cantidad > 0``. This
    function does NOT commit; the caller wraps in a transaction.
    """
    await db.execute(
        """
        DELETE FROM stock_sin_ubicacion
        WHERE producto_id = ? AND cantidad = 0
        """,
        (producto_id,),
    )


async def list_all_with_producto(db: aiosqlite.Connection) -> list[dict]:
    """Return every row in ``stock_sin_ubicacion`` joined with its ``productos``
    row, ordered by ``updated_at DESC`` (most recently moved to the bucket
    first) then ``producto_sku ASC`` as a stable tiebreaker.

    R1 invariant guarantees every row returned has ``cantidad > 0`` (no
    zero-orphans), so there is no need for a ``WHERE cantidad > 0`` filter
    here — kept defensively inline for clarity.

    Returns a list of dicts, one per bucket row:
      * ``producto_sku``        — bucket row's ``producto_id`` (= productos.sku).
      * ``producto_descripcion``— joined from ``productos.descripcion``; may be
        ``""`` (empty string) if a product was deleted without cascading — the
        ``stock_sin_ubicacion`` table has ``ON DELETE CASCADE`` on the FK
        (migration 015:1), so orphan rows cannot happen in practice, but the
        ``LEFT JOIN`` keeps the endpoint robust if a future writer bypasses
        FK enforcement.
      * ``cantidad``           — bucket qty.
      * ``updated_at``         — last bucket-modified timestamp.

    Spec anchor: Slice 6 admin ``GET /productos/sin-ubicacion`` (Point 5).
    """
    async with db.execute(
        """
        SELECT
            s.producto_id AS producto_sku,
            COALESCE(p.descripcion, '') AS producto_descripcion,
            s.cantidad AS cantidad,
            s.updated_at AS updated_at
          FROM stock_sin_ubicacion s
          LEFT JOIN productos p ON p.sku = s.producto_id
         WHERE s.cantidad > 0
         ORDER BY s.updated_at DESC, s.producto_id ASC
        """,
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]