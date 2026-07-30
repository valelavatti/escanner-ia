"""Tests for the B6 assign-overwrite edge case (Slice 6 — Phase B follow-up).

Scenario
--------

Slice 2b shipped :func:`ubicacion_repository.unassign_producto_from_ubicacion`
with the correct leftover-stock-to-bucket + ``desasignacion`` audit-fix
behavior. Slice 2b's :func:`assign_producto_to_ubicacion` raised
``UbicacionOcupadaError`` whenever the target cell was already occupied
(same OR different product) — the FE admin modal had to call unassign
FIRST before reassigning the cell to a new product.

Slice 6 closes that UX gap: the assign flow now detects a DIFFERENT
previous occupant and delegates the cleanup to the existing unassign
surgery (moves the previous occupant's stock into ITS bucket with a
proper ``desasignacion`` audit row) BEFORE running the assign for the
new product. The same-product case still raises
``UbicacionOcupadaError`` (preserves the historical tag-only guard so
the FE can detect "no rewrite needed").

Coverage
--------

- **B6.A** — assign Q to U1 with ``entered_qty=0`` when U1 holds P with
  stock=10. Expect U1 product=Q stock=0, P bucket=10, Q bucket=0, exactly
  one ``desasignacion`` row for P (qty=10, stock_general_anterior=10,
  stock_general_nuevo=0), ZERO ``asignacion`` row for Q (remainder=0 per
  REQ-B-008).
- **B6.B** — assign Q to U1 with ``entered_qty=5`` when U1 holds P with
  stock=10. Expect U1 product=Q stock=5, P bucket=10, Q bucket=0, one
  ``desasignacion`` row for P (qty=10), ONE ``asignacion`` row for Q at
  U1 (qty=5, stock_general_anterior=0, stock_general_nuevo=5).
- **B6.C** — defensive regression: when U1 already holds P and the user
  assigns P again, the function still raises ``UbicacionOcupadaError``
  (the same-product tag-only guard preserved by Slice 6).

Carry-forward #3 from prior slices: each test creates ONE shared
``estante_id`` via :func:`estante_factory` and uses distinct
``(fila, columna)`` per :func:`ubicacion_factory` call (migration 014's
partial unique index on ``estantes.nombre`` + ``ubicaciones.qr_valor``
UNIQUE requires both distinct).

Spec anchors: REQ-B-001..010, REQ-B-008 (no ``asignacion`` row when
remainder = 0), REQ-X-006 (slice-6 follow-up scenario B6).
"""

from __future__ import annotations

import pytest

from app.repositories import movimiento_repository as _mov_repo
from app.repositories import stock_sin_ubicacion_repository as _bucket_repo
from app.repositories import ubicacion_repository as _ub_repo
from app.repositories.ubicacion_repository import UbicacionOcupadaError


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test-scoped async helpers (kept parallel to test_ubicacion_repository.py).
# ---------------------------------------------------------------------------


async def _fetch_all(db, sql, params):
    """Run ``sql`` with ``params``, return a list of ``dict`` (one per row)."""
    async with db.execute(sql, params) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def _scalar(db, sql, params):
    """Run ``sql`` with ``params``, return the first column of the first row as int.

    Returns ``0`` when the query produces no row or when the cell is NULL —
    a defensive convenience for the ``COUNT(*)`` predicates used throughout
    this slice (avoids the operator-precedence trap of
    ``int(row[0]) if row else 0 == 0``, which Python parses as
    ``int(row[0]) if row else (0 == 0)`` and would silently equate to True
    in the else-branch — masking real assertion failures).
    """
    async with db.execute(sql, params) as cursor:
        row = await cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


async def _read_ub_row(db, ubicacion_id):
    """Return ``{producto_id, stock_actual}`` for the ubicacion, or ``None``."""
    async with db.execute(
        "SELECT producto_id, stock_actual FROM ubicaciones WHERE id = ?",
        (ubicacion_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return dict(row) if row else None


async def _bucket_qty(db, producto_id):
    """Boilerplate alias for ``stock_sin_ubicacion_repository.get_cantidad``."""
    return await _bucket_repo.get_cantidad(db, producto_id)


async def _assign_with_qty(db, ubicacion_id, producto_id, qty, usuario_id=None):
    """Shorthand: call the surgery'd assign with an explicit ``entered_qty``."""
    return await _ub_repo.assign_producto_to_ubicacion(
        db,
        ubicacion_id=ubicacion_id,
        producto_id=producto_id,
        usuario_id=usuario_id,
        entered_qty=qty,
    )


async def _build_p_at_u1_qty_10(
    db,
    estante_factory,
    producto_factory,
    ubicacion_factory,
    *,
    p_sku,
    estante_nombre,
):
    """Run the common B6 arrange phase: assign P to U1 with ``entered_qty=10``.

    Returns ``(p, u1, estante_id)``.
    State after this returns:
      * ``ubicaciones[u1].producto_id``  = P
      * ``ubicaciones[u1].stock_actual`` = 10
      * ``stock_sin_ubicacion[p]``         = 0 (row absent — never populated)
      * ``movimientos`` has 1 ``asignacion`` row for P at U1 qty=10.
    """
    p = await producto_factory(sku=p_sku)
    estante_id = await estante_factory(nombre=estante_nombre)
    u1 = await ubicacion_factory(estante_id=estante_id, fila=1, columna=1)

    # Assign P to U1 with entered_qty=10. Bucket empty for P → drain=0,
    # remainder=10. asignacion row written qty=10.
    await _assign_with_qty(db, u1, p, qty=10)
    return p, u1, estante_id


# ---------------------------------------------------------------------------
# B6.A — assign Q to U1 (which holds P stock=10) with entered_qty=0.
# Expect P's 10 in P's bucket, U1 holds Q at stock=0, Q's own bucket=0,
# exactly one desasignacion row for P (with P's pre-unassign stock_general
# snapshots: anterior=10, nuevo=0), ZERO asignacion row for Q (remainder=0
# per REQ-B-008).
# ---------------------------------------------------------------------------


class TestAssignOverwriteWithQtyZero:
    """B6.A — assign Q to an occupied cell with entered_qty=0 (tag-only).

    Edge case: P's stock at U1 MUST be moved into P's bucket, NOT silently
    reattributed to Q and NOT left rotting in the cell after Q is tagged.
    """

    async def test_b6a_assign_overwrite_qty_zero_moves_p_to_bucket(
        self, db_session, producto_factory, estante_factory, ubicacion_factory
    ):
        p, u1, _ = await _build_p_at_u1_qty_10(
            db_session, estante_factory, producto_factory, ubicacion_factory,
            p_sku="B6A-P", estante_nombre="B6A Shelf",
        )
        # Sanity: U1 holds P@10, P's bucket is empty, Q doesn't exist yet.
        ub = await _read_ub_row(db_session, u1)
        assert ub["producto_id"] == p
        assert ub["stock_actual"] == 10
        assert await _bucket_qty(db_session, p) == 0

        # Action: assign Q to U1 with entered_qty=0 (the edge case).
        q = await producto_factory(sku="B6A-Q")
        result = await _assign_with_qty(db_session, u1, q, qty=0)
        assert result is True

        # U1 now holds Q at stock=0.
        ub = await _read_ub_row(db_session, u1)
        assert ub["producto_id"] == q
        assert ub["stock_actual"] == 0

        # P's 10 units moved to P's bucket (REQ-B-002 via the delegated
        # unassign surgery); Q's bucket is still 0 (Q never had any).
        assert await _bucket_qty(db_session, p) == 10
        assert await _bucket_qty(db_session, q) == 0

        # P's stock_general: Slice 8 Bug 1 fix means `get_producto_stock_total`
        # now INCLUDES the bucket qty, so P (= 0 physical at any cell + 10 in
        # the bucket) reports sg = 10 (was 0 pre-Slice-8 — the bucket was
        # silently dropped by the old physical-only sum). Q's stock_general
        # is 0 (entered_qty=0, Q has no physical cell AND no bucket row).
        assert await _mov_repo.get_producto_stock_total(db_session, p) == 10
        assert await _mov_repo.get_producto_stock_total(db_session, q) == 0

        # Desasignacion row for P: exactly one, with the OUTGOING (P)
        # product's pre-unassign stock_general snapshots (anterior=10,
        # nuevo=0).REQ-B-003 audit-fix at the unassign surgery.
        rows = await _fetch_all(
            db_session,
            "SELECT producto_id, ubicacion_id, cantidad, stock_anterior, "
            "stock_nuevo, stock_general_anterior, stock_general_nuevo, tipo "
            "FROM movimientos WHERE tipo = 'desasignacion' AND producto_id = ? "
            "AND ubicacion_id = ?",
            (p, u1),
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["producto_id"] == p  # OUTGOING product
        assert row["cantidad"] == 0  # historical shape: single-timestamp un-tag
        assert row["stock_anterior"] == 10  # qty that left the cell → bucket
        assert row["stock_nuevo"] == 0  # cell zeroed
        assert row["stock_general_anterior"] == 10  # P's pre-unassign total
        assert row["stock_general_nuevo"] == 0  # P's post-unassign (in bucket)

        # NO asignacion row for Q at U1 — remainder = entered_qty(0) -
        # bucket_qty(0 for Q) = 0; REQ-B-008 forbids the row when remainder=0.
        count_q_asignacion = await _scalar(
            db_session,
            "SELECT COUNT(*) FROM movimientos "
            "WHERE tipo = 'asignacion' AND producto_id = ? AND ubicacion_id = ?",
            (q, u1),
        )
        assert count_q_asignacion == 0

        # NO rescate_sin_ubicacion row was written by the assign flow — Q had
        # no bucket to drain (bucket_qty(Q)=0 → drain_amount=0).
        count_q_rescate = await _scalar(
            db_session,
            "SELECT COUNT(*) FROM movimientos "
            "WHERE tipo = 'rescate_sin_ubicacion' AND producto_id = ?",
            (q,),
        )
        assert count_q_rescate == 0


# ---------------------------------------------------------------------------
# B6.B — assign Q to U1 (which holds P stock=10) with entered_qty=5.
# Expect P's 10 in P's bucket, U1 holds Q at stock=5, Q's own bucket=0,
# one desasignacion row for P (qty=10, anterior=10, nuevo=0), ONE
# asignacion row for Q at U1 (qty=5, anterior=0, nuevo=5).
# ---------------------------------------------------------------------------


class TestAssignOverwriteWithQtyFive:
    """B6.B — assign Q to an occupied cell with entered_qty=5 (count + tag).

    The previous occupant (P) is unassigned first (stock to P's bucket); then
    Q enters at qty=5 (no bucket drain for Q since Q has no bucket).
    """

    async def test_b6b_assign_overwrite_qty_five_writes_asignacion_for_q(
        self, db_session, producto_factory, estante_factory, ubicacion_factory
    ):
        p, u1, _ = await _build_p_at_u1_qty_10(
            db_session, estante_factory, producto_factory, ubicacion_factory,
            p_sku="B6B-P", estante_nombre="B6B Shelf",
        )
        # Sanity: U1 holds P@10, P's bucket empty.
        ub = await _read_ub_row(db_session, u1)
        assert ub["producto_id"] == p
        assert ub["stock_actual"] == 10

        # Action: assign Q to U1 with entered_qty=5.
        q = await producto_factory(sku="B6B-Q")
        result = await _assign_with_qty(db_session, u1, q, qty=5)
        assert result is True

        # U1 now holds Q at stock=5.
        ub = await _read_ub_row(db_session, u1)
        assert ub["producto_id"] == q
        assert ub["stock_actual"] == 5

        # P's 10 in P's bucket; Q's bucket still 0.
        assert await _bucket_qty(db_session, p) == 10
        assert await _bucket_qty(db_session, q) == 0

        # Stock_general invariants (Slice 8 Bug 1 fix): P's `get_producto_stock_total`
        # now INCLUDES the bucket (10 in P's bucket + 0 physical = 10); Q's
        # = 5 (the physical stock at U1 + 0 in bucket). REQ-B-009.
        assert await _mov_repo.get_producto_stock_total(db_session, p) == 10
        assert await _mov_repo.get_producto_stock_total(db_session, q) == 5

        # Desasignacion row for P at U1: exactly one, with P's snapshots.
        rows = await _fetch_all(
            db_session,
            "SELECT producto_id, ubicacion_id, cantidad, stock_anterior, "
            "stock_nuevo, stock_general_anterior, stock_general_nuevo, tipo "
            "FROM movimientos WHERE tipo = 'desasignacion' AND producto_id = ? "
            "AND ubicacion_id = ?",
            (p, u1),
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["producto_id"] == p
        assert row["stock_anterior"] == 10
        assert row["stock_nuevo"] == 0
        assert row["stock_general_anterior"] == 10
        assert row["stock_general_nuevo"] == 0

        # Asignacion row for Q at U1: exactly one, qty=5 (the remainder
        # since Q had no bucket to drain). Snapshots: anterior=0 (Q had no
        # prior stock anywhere); nuevo=5 (Q's new total stock_general).
        rows = await _fetch_all(
            db_session,
            "SELECT producto_id, ubicacion_id, cantidad, stock_anterior, "
            "stock_nuevo, stock_general_anterior, stock_general_nuevo, tipo "
            "FROM movimientos WHERE tipo = 'asignacion' AND producto_id = ? "
            "AND ubicacion_id = ?",
            (q, u1),
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["producto_id"] == q
        assert row["cantidad"] == 5
        assert row["stock_anterior"] == 0
        assert row["stock_nuevo"] == 5
        assert row["stock_general_anterior"] == 0
        assert row["stock_general_nuevo"] == 5

        # NO rescate_sin_ubicacion row for Q — Q's bucket was empty (drain=0).
        count_q_rescate = await _scalar(
            db_session,
            "SELECT COUNT(*) FROM movimientos "
            "WHERE tipo = 'rescate_sin_ubicacion' AND producto_id = ?",
            (q,),
        )
        assert count_q_rescate == 0


# ---------------------------------------------------------------------------
# B6.C — defensive regression: the same-product case MUST still raise
# ``UbicacionOcupadaError``. Slice 6 preserves this historical tag-only
# guard rather than silently re-zeroing the cell when the FE asks for a
# no-op re-tag of the same product.
# ---------------------------------------------------------------------------


class TestAssignSameProductStillRaisesUbicacionOcupadaError:
    """B6.C — defensive regression for the preserved same-product guard."""

    async def test_b6c_same_product_reassign_raises_ocupada(
        self, db_session, producto_factory, estante_factory, ubicacion_factory
    ):
        p, u1, _ = await _build_p_at_u1_qty_10(
            db_session, estante_factory, producto_factory, ubicacion_factory,
            p_sku="B6C-P", estante_nombre="B6C Shelf",
        )
        # Sanity: U1 holds P@10.
        ub = await _read_ub_row(db_session, u1)
        assert ub["producto_id"] == p
        assert ub["stock_actual"] == 10

        # Action: re-assign P to U1 with entered_qty=5 — should raise.
        with pytest.raises(UbicacionOcupadaError):
            await _assign_with_qty(db_session, u1, p, qty=5)

        # State UNCHANGED — the raise happened BEFORE any mutation; no
        # bucket row created, no extra movimiento written, U1 still holds
        # P at stock=10.
        ub = await _read_ub_row(db_session, u1)
        assert ub["producto_id"] == p
        assert ub["stock_actual"] == 10
        assert await _bucket_qty(db_session, p) == 0

        # Exactly ONE ``asignacion`` row for P at U1 (the setup one with
        # qty=10 — no extra row from the failed re-tag attempt).
        rows = await _fetch_all(
            db_session,
            "SELECT producto_id, ubicacion_id, cantidad FROM movimientos "
            "WHERE tipo = 'asignacion' AND producto_id = ? AND ubicacion_id = ?",
            (p, u1),
        )
        assert len(rows) == 1
        assert rows[0]["cantidad"] == 10

        # ZERO ``desasignacion`` rows for P anywhere (the failed same-product
        # reassign must NOT have triggered the unassign-delegate path — that
        # path is only for the DIFFERENT-product case).
        count_p_desasignacion = await _scalar(
            db_session,
            "SELECT COUNT(*) FROM movimientos "
            "WHERE tipo = 'desasignacion' AND producto_id = ?",
            (p,),
        )
        assert count_p_desasignacion == 0