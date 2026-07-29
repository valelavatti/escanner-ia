"""Tests for the B7 scanner-overwrite-to-bucket regression (Slice 7).

Scenario
--------

The app has TWO code paths for reassigning a cell to a product:

1. ``POST /movimientos`` → ``movimiento_repository._create_movimiento_once``
   (the path the SCANNER uses, via ``scanner/+page.svelte:handleSave`` →
   ``createMovimiento({producto_sku, ubicacion_id, cantidad, tipo: mode})``).
2. ``PUT /ubicaciones/{id}/assign`` →
   ``ubicacion_repository.assign_producto_to_ubicacion`` (admin path; the
   one Slice 2b's surgery lives on).

Slice 2b correctly routed the OUTGOING product's units into its
``stock_sin_ubicacion`` bucket on the admin path (#2). Slice 2b did NOT
touch path #1 — the scanner's path. As a result, when the user scanned a
new product onto a cell that already held a DIFFERENT product with
positive stock, path #1 wrote an audit ``desasignacion`` row (good for
the audit trail) but **never moved the OUTGOING product's units into the
bucket**. The subsequent ``UPDATE ubicaciones SET stock_actual = ?``
silently OVERWROTE the cell — and the OUTGOING product's units vanished
from the data model (the user's bug report after Slice 6: *"el stock se
 pierde al pisar un producto en el scanner"*).

Slice 7 closes the gap: the ``is_reassignment`` branch in
``_create_movimiento_once`` now also calls
``stock_sin_ubicacion_repository.upsert_add(db, old_producto_id,
ubicacion["stock_actual"])`` so the OUTGOING product's units land in ITS
bucket — same behavior the Slice 2b admin path already had. The audit
``desasignacion`` row's ``stock_general_nuevo`` for the OUTGOING product
now equals its ``stock_general_anterior`` (units conserved, just moved to
the bucket — NOT decremented, NOT lost).

Coverage
--------

All three variants drive the SCANNER path (`create_movimiento`,
``tipo='alta'``) — NOT the admin path. A shared helper
``_arrange_p_at_u1_qty_10`` reuses the codebase convention of "shared
``estante_id`` + distinct ``fila/columna`` per cell" so the partial
UNIQUE index on ``estantes.nombre`` and the UNIQUE on
``ubicaciones.qr_valor`` both hold.

- **B7** — overwrite U1 (holding P at stock=10) with Q entering qty=5.
  Expect U1 now holds Q at stock=5, P's bucket=10, Q's bucket=0, a
  ``desasignacion`` row for P (qty=0, stock_anterior=10, stock_nuevo=0,
  stock_general_anterior=10, stock_general_nuevo=10 — conservation), and
  an ``asignacion`` row for Q.
- **B7-edge** — overwrite with Q entering qty=0. P's 10 units STILL
  move to P's bucket (the audit sweep fires regardless of the new
  product's entered qty); U1 holds Q at stock=0; Q's bucket=0.
- **B7-same-product** — try to reassign P → P at U1. ``is_reassignment``
  is False (because ``old_producto_id == producto_sku``) — so NO
  ``desasignacion`` row, NO bucket UPSERT happen. Only the ``alta`` row
  accumulates P's stock.

Carry-forward #3 from prior slices: each test creates ONE shared
``estante_id`` via :func:`estante_factory` and uses distinct
``(fila, columna)`` per :func:`ubicacion_factory` call. Carry-forward #1:
:func:`movimiento_repository.get_producto_stock_total` returns
PHYSICAL + Suelto sum ONLY (NOT bucket), so the snapshot
``stock_general_anterior`` of the OLD product at reassign time reflects
its physical stock at U1 (which is 10 immediately before the cell is
overwritten).

Spec anchors: REQ-B-002 (UPSERT to bucket for the OUTGOING product),
REQ-B-003 (audit mis-attribution fix — OLD product's snapshot, not NEW),
REQ-B-009 (stock_general invariant: physical + bucket == stock_general
for the OLD product after reassign), REQ-X-006 (slice-7 follow-up
scenario B7).
"""

from __future__ import annotations

import pytest

from app.repositories import movimiento_repository as _mov_repo
from app.repositories import stock_sin_ubicacion_repository as _bucket_repo


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test-scoped async helpers (parallel to test_assign_overwrite_edge_case.py).
# ---------------------------------------------------------------------------


async def _fetch_all(db, sql, params):
    """Run ``sql`` with ``params``, return a list of ``dict`` (one per row)."""
    async with db.execute(sql, params) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def _scalar(db, sql, params):
    """Run ``sql`` with ``params``, return the first column of the first row as int. Defaults to 0 (defensive
    convenience for ``COUNT(*)`` predicates — matches the convention in test_assign_overwrite_edge_case.py)."""
    async with db.execute(sql, params) as cursor:
        row = await cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


async def _read_ub_row(db, ubicacion_id):
    """Return ``{producto_id, stock_actual}`` for ``ubicacion_id``, or ``None``."""
    async with db.execute(
        "SELECT producto_id, stock_actual FROM ubicaciones WHERE id = ?",
        (ubicacion_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return dict(row) if row else None


async def _bucket_qty(db, producto_id):
    """Boilerplate alias for ``stock_sin_ubicacion_repository.get_cantidad``."""
    return await _bucket_repo.get_cantidad(db, producto_id)


async def _arrange_p_at_u1_qty_10(
    db, estante_factory, producto_factory, ubicacion_factory,
    *, p_sku, estante_nombre,
):
    """Run the common B7 arrange phase via the SCANNER path.

    Uses ``movimiento_repository.create_movimiento(..., tipo='alta',
    cantidad=10)`` — the exact code path the scanner UI calls — NOT the
    admin assign surgery in ``ubicacion_repository``.

    Returns ``(p, u1, u2, estante_id)``.
    State after this returns:
      * ``ubicaciones[u1].producto_id``  = P
      * ``ubicaciones[u1].stock_actual`` = 10
      * ``stock_sin_ubicacion[p]``        = 0 (row absent — never populated)
      * ``movimientos`` has 1 ``asignacion`` row for P at U1 qty=10 +
        1 ``alta`` row for P at U1 qty=10 stock_anterior=0 stock_nuevo=10.
      * ``u2`` is created empty (no product, stock=0) so the caller can
        use it for multi-ubicacion checks if desired.
    """
    p = await producto_factory(sku=p_sku)
    estante_id = await estante_factory(nombre=estante_nombre)
    u1 = await ubicacion_factory(estante_id=estante_id, fila=1, columna=1)
    u2 = await ubicacion_factory(estante_id=estante_id, fila=2, columna=1)

    # SCANNER PATH: alta P at U1 with qty=10. is_new_assignment=True (no
    # prior occupant) → an `asignacion` row is written, then the `alta`
    # row is written, then ubicaciones.stock_actual goes 0→10 and
    # producto_id goes NULL→P. No bucket UPSERT (the prior occupant was
    # NULL, not a DIFFERENT product — is_reassignment=False).
    await _mov_repo.create_movimiento(
        db, usuario_id=None, producto_sku=p,
        ubicacion_id=u1, cantidad=10, tipo="alta",
    )
    return p, u1, u2, estante_id


# ---------------------------------------------------------------------------
# B7 — main scenario: scanner-overwrite U1 (P@10) with Q entering qty=5.
# Expect P's 10 → P's bucket (THE FIX); U1 holds Q@5; Q's bucket stays 0;
# one desasignacion row for P (anterior=10, nuevo=0, sg_anterior=10,
# sg_nuevo=10 — conservation per Slice 7); one asignacion row for Q.
# ---------------------------------------------------------------------------


class TestScannerReassignMovesOutgoingProductToBucket:
    """B7 — the user's exact bug report: "el stock se pierde al pisar un
    producto en el scanner". Without Slice 7, path #1 (POST /movimientos)
    writes the desasignacion audit row but NEVER moves the OUTGOING
    product's units to the bucket — they vanish when the subsequent
    ``UPDATE ubicaciones SET stock_actual = ?`` overwrites the cell."""

    async def test_b7_overwrite_moves_p_to_bucket_and_q_owns_u1(
        self, db_session, producto_factory, estante_factory, ubicacion_factory
    ):
        p, u1, _, _ = await _arrange_p_at_u1_qty_10(
            db_session, estante_factory, producto_factory, ubicacion_factory,
            p_sku="B7-P", estante_nombre="B7 Shelf",
        )
        # Sanity: U1 holds P@10, P's bucket empty (no reassignment has
        # happened yet — the alta path only triggers is_new_assignment, not
        # is_reassignment).
        ub = await _read_ub_row(db_session, u1)
        assert ub["producto_id"] == p
        assert ub["stock_actual"] == 10
        assert await _bucket_qty(db_session, p) == 0

        # Action: scanner overwrite U1 with Q entering qty=5 (scanner path).
        q = await producto_factory(sku="B7-Q")
        await _mov_repo.create_movimiento(
            db_session, usuario_id=None, producto_sku=q,
            ubicacion_id=u1, cantidad=5, tipo="alta",
        )

        # U1 now holds Q at stock=5 (the ubicaciones UPDATE that previously
        # SILENTLY OVERWROTE P's 10 now happens AFTER P's 10 went to the
        # bucket — units conserved).
        ub = await _read_ub_row(db_session, u1)
        assert ub["producto_id"] == q
        assert ub["stock_actual"] == 5

        # THE FIX: P's 10 units now live in P's bucket, NOT vanished.
        # Q's bucket stays 0 — Q never had a bucket UPSERT (the Slice 7
        # addition only ever UPSERTs the OUTGOING old_producto_id; the
        # incoming Q drinks from the alta row, not the bucket).
        assert await _bucket_qty(db_session, p) == 10
        assert await _bucket_qty(db_session, q) == 0

        # REQ-B-009 invariant at the OLD product: stock_general(P) as
        # reported by get_producto_stock_total (physical + Suelto only,
        # per carry-forward #1) is now 0 — P has no physical cell anymore.
        # The 10 units live ONLY in the bucket — which is the expected
        # OUT-of-stock_general state (out of physical = in bucket pending
        # rescue). When Slice 6 Phase C's endpoint logic adds the bucket
        # qty back at the API boundary, the displayed stock_total(P) is
        # 0 + 10 = 10 (the user-visible conservation).
        assert await _mov_repo.get_producto_stock_total(db_session, p) == 0
        assert await _mov_repo.get_producto_stock_total(db_session, q) == 5

    async def test_b7_desasignacion_audit_row_has_conservation_snapshots(
        self, db_session, producto_factory, estante_factory, ubicacion_factory
    ):
        """The audit ``desasignacion`` row for the OUTGOING product MUST
        carry P's pre-reassign stock_general as ``stock_general_anterior``
        AND — per Slice 7 — the same value as
        ``stock_general_nuevo`` (units conserved, just relocated to the
        bucket). The SLICE-2b shape (anterior - stock_actual) is exactly
        what this branch MUST NOT do anymore in the scanner path."""
        p, u1, _, _ = await _arrange_p_at_u1_qty_10(
            db_session, estante_factory, producto_factory, ubicacion_factory,
            p_sku="B7A-P", estante_nombre="B7A Shelf",
        )
        q = await producto_factory(sku="B7A-Q")
        await _mov_repo.create_movimiento(
            db_session, usuario_id=None, producto_sku=q,
            ubicacion_id=u1, cantidad=5, tipo="alta",
        )

        # Exactly one desasignacion row for P at U1 with the Slice 7
        # conservation shape: anterior=10 (P's pre-reassign total),
        # nuevo=10 (same — units are conserved, just relocated to bucket).
        rows = await _fetch_all(
            db_session,
            "SELECT producto_id, ubicacion_id, cantidad, stock_anterior, "
            "stock_nuevo, stock_general_anterior, stock_general_nuevo, tipo "
            "FROM movimientos WHERE tipo = 'desasignacion' "
            "AND producto_id = ? AND ubicacion_id = ?",
            (p, u1),
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["producto_id"] == p  # OUTGOING product (REQ-B-003 audit-fix)
        assert row["cantidad"] == 0  # historical shape: tag-only event
        assert row["stock_anterior"] == 10  # qty that left the cell
        assert row["stock_nuevo"] == 0  # cell zeroed
        # Slice 7 conservation: the audit row no longer claims P's
        # stock_general dropped by 10 (it would have lied pre-fix — the
        # units didn't vanish, they went to the bucket).
        assert row["stock_general_anterior"] == 10
        assert row["stock_general_nuevo"] == 10

        # At least one desasignacion row for P at U1 (the orchestrator's
        # spec asked for "count >= 1" — our assertion is stricter: exactly 1).
        count_p_desasig = await _scalar(
            db_session,
            "SELECT COUNT(*) FROM movimientos "
            "WHERE tipo = 'desasignacion' AND producto_id = ? AND ubicacion_id = ?",
            (p, u1),
        )
        assert count_p_desasig == 1

    async def test_b7_writes_asignacion_row_for_incoming_q(
        self, db_session, producto_factory, estante_factory, ubicacion_factory
    ):
        """The ``asignacion`` row for the incoming NEW product Q MUST be
        written at U1 (Slice 7 fix only touches the OUTGOING product's
        branch; the existing ``is_new_assignment or is_reassignment``
        block at line ~215 keeps producing the Q `asignacion` audit row
        so Q's tenure is tracked identically to the admin path #2)."""
        p, u1, _, _ = await _arrange_p_at_u1_qty_10(
            db_session, estante_factory, producto_factory, ubicacion_factory,
            p_sku="B7B-P", estante_nombre="B7B Shelf",
        )
        q = await producto_factory(sku="B7B-Q")
        await _mov_repo.create_movimiento(
            db_session, usuario_id=None, producto_sku=q,
            ubicacion_id=u1, cantidad=5, tipo="alta",
        )

        # Q has exactly one asignacion row at U1. Per Slice 2b's invariant
        # (the path #1 hit before Slice 2b's surgery), the asignacion row
        # carries Q's pre-alta stock_general (0) for BOTH anterior and
        # nuevo — the asignacion event itself is a tag-only event with
        # qty=0; the alta row separately records the qty=5 increment.
        rows = await _fetch_all(
            db_session,
            "SELECT producto_id, ubicacion_id, cantidad, stock_anterior, "
            "stock_nuevo, stock_general_anterior, stock_general_nuevo, tipo "
            "FROM movimientos WHERE tipo = 'asignacion' "
            "AND producto_id = ? AND ubicacion_id = ?",
            (q, u1),
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["producto_id"] == q
        assert row["cantidad"] == 0
        assert row["stock_general_anterior"] == 0
        assert row["stock_general_nuevo"] == 0

        # And the alta row for Q exists — that's the row that records
        # the qty=5 the user scanned onto the cell.
        alta_rows = await _fetch_all(
            db_session,
            "SELECT producto_id, ubicacion_id, cantidad, stock_anterior, "
            "stock_nuevo, tipo FROM movimientos WHERE tipo = 'alta' "
            "AND producto_id = ? AND ubicacion_id = ?",
            (q, u1),
        )
        assert len(alta_rows) == 1
        alta = alta_rows[0]
        assert alta["cantidad"] == 5
        assert alta["stock_anterior"] == 0  # P's prior qty in U1 isn't Q's prior
        assert alta["stock_nuevo"] == 5


# ---------------------------------------------------------------------------
# B7-edge — overwrite Q entering qty=0. The audit sweep fires regardless
# of the new product's entered qty — the OLD product's units MUST still
# go to its bucket. Matches the user's edge case (scanned onto a cell
# with the wrong qty=0 first, then realizing the previous product's
# units need rescuing).
# ---------------------------------------------------------------------------


class TestScannerReassignEdgeQtyZeroStillMovesOutgoingProductToBucket:
    """B7-edge — the OLD product's units go to its bucket even when the
    NEW product's ``alta`` carried ``cantidad=0``. The audit sweep is
    keyed on ``is_reassignment`` (a DIFFERENT prior occupant exists), NOT
    on the new product's entered qty — so the prior occupant's cleanup
    MUST run unconditionally when the cell is overwritten."""

    async def test_b7_edge_qty_zero_moves_p_to_bucket_keep_u1_at_zero(
        self, db_session, producto_factory, estante_factory, ubicacion_factory
    ):
        p, u1, _, _ = await _arrange_p_at_u1_qty_10(
            db_session, estante_factory, producto_factory, ubicacion_factory,
            p_sku="B7E-P", estante_nombre="B7E Shelf",
        )
        q = await producto_factory(sku="B7E-Q")

        # SCANNER PATH: alta Q at U1 with qty=0 — the edge case.
        await _mov_repo.create_movimiento(
            db_session, usuario_id=None, producto_sku=q,
            ubicacion_id=u1, cantidad=0, tipo="alta",
        )

        # U1 now holds Q at stock=0 (the alta additive-incremented 0 onto
        # the prior 0 that _get_stock_anterior returned for Q — the
        # "fresh start for DIFFERENT prior product" rule at
        # ``_get_stock_anterior``:92-93).
        ub = await _read_ub_row(db_session, u1)
        assert ub["producto_id"] == q
        assert ub["stock_actual"] == 0

        # P's 10 EMERGED into P's bucket (the audit sweep fired because
        # ``is_reassignment`` is True regardless of qty). WITHOUT the
        # Slice 7 fix, qty=0 would be exactly the failure mode where the
        # user sees "the bucket of P stayed at 0 and P's units are gone".
        assert await _bucket_qty(db_session, p) == 10
        assert await _bucket_qty(db_session, q) == 0

        # P's physical+U1 stock_general is now 0 (all in bucket — same
        # state as B7 main, just reached via a qty=0 alta).
        assert await _mov_repo.get_producto_stock_total(db_session, p) == 0
        assert await _mov_repo.get_producto_stock_total(db_session, q) == 0

        # P's desasignacion row ALSO exists under the edge case (the
        # audit sweep is not gated on the new product's qty).
        count_p_desasig = await _scalar(
            db_session,
            "SELECT COUNT(*) FROM movimientos "
            "WHERE tipo = 'desasignacion' AND producto_id = ?",
            (p,),
        )
        assert count_p_desasig == 1


# ---------------------------------------------------------------------------
# B7-same-product — try to reassign P → P at U1. ``is_reassignment`` is
# False (because ``old_producto_id == producto_sku``), so neither the
# ``desasignacion`` row nor the bucket UPSERT happen. Only the ``alta``
# accumulates P's stock at U1 — exactly the pre-Slice-7 behavior for this
# corner. This is a defensive regression lock so a future "always route
# to bucket" over-eager refactor of path #1 doesn't accidentally start
# cloning P's units into P's own bucket when the user just keeps scanning
# more of P.
# ---------------------------------------------------------------------------


class TestScannerSameProductReassignDoesNotTouchBucket:
    """B7-same-product — defensive lock for the same-product non-event.

    Re-scanning the SAME product onto a cell it already holds is a
    common high-frequency scanner gesture: the user adds more stock of
    P to U1. That MUST NOT trigger the reassignment branch (P≠P is
    False) — only the alta row should be written, accumulating P's
    stock onto U1. Bucket UPSERT must NOT fire (P is not losing the
    cell); the desasignacion row MUST NOT be written (no OUTGOING
    product exists)."""

    async def test_b7_same_product_reassign_does_not_upsert_bucket_nor_desasigna(
        self, db_session, producto_factory, estante_factory, ubicacion_factory
    ):
        p, u1, _, _ = await _arrange_p_at_u1_qty_10(
            db_session, estante_factory, producto_factory, ubicacion_factory,
            p_sku="B7S-P", estante_nombre="B7S Shelf",
        )
        # Sanity: U1 holds P@10, P's bucket empty.
        ub = await _read_ub_row(db_session, u1)
        assert ub["producto_id"] == p
        assert ub["stock_actual"] == 10
        assert await _bucket_qty(db_session, p) == 0

        # Action: alta MORE of P at U1 (qty=3, scanner same-product gesture).
        await _mov_repo.create_movimiento(
            db_session, usuario_id=None, producto_sku=p,
            ubicacion_id=u1, cantidad=3, tipo="alta",
        )

        # The alta is additive: U1 = 10 + 3 = 13.
        ub = await _read_ub_row(db_session, u1)
        assert ub["producto_id"] == p
        assert ub["stock_actual"] == 13

        # Bucket of P STILL 0 — same-product is NOT a reassignment, so
        # the Slice 7 UPSERT does not fire.
        assert await _bucket_qty(db_session, p) == 0

        # ZERO desasignacion rows for P anywhere (the same-product alta
        # path is a pure stock increment; no OUTGOING product existed).
        count_p_desasig = await _scalar(
            db_session,
            "SELECT COUNT(*) FROM movimientos "
            "WHERE tipo = 'desasignacion' AND producto_id = ?",
            (p,),
        )
        assert count_p_desasig == 0

        # Exactly ONE alta row for P at U1 written THIS test, with qty=3
        # added on top of the 10 the setup wrote (so 13 cumulative). And
        # the stock_general invariant is intact (P has only physical
        # stock at U1; 13 = sg(P) because bucket is 0).
        # (The setup wrote a separate qty=10 alta row before this; assert
        # the LATEST alta row carries the qty=3 increment.)
        rows = await _fetch_all(
            db_session,
            "SELECT producto_id, ubicacion_id, cantidad, stock_anterior, "
            "stock_nuevo, tipo FROM movimientos WHERE tipo = 'alta' "
            "AND producto_id = ? AND ubicacion_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (p, u1),
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["cantidad"] == 3
        assert row["stock_anterior"] == 10
        assert row["stock_nuevo"] == 13
        assert await _mov_repo.get_producto_stock_total(db_session, p) == 13