"""Tests for Slice 8 Bug 2 fix + Feature — the explicit ``drain_bucket_qty``
checkbox flow on the scanner's path #1 (``POST /movimientos`` →
``movimiento_repository._create_movimiento_once``).

WHY THIS FIX
------------
Bug 2: the alta path NEVER drained the bucket — when a user scanned a
product onto a fresh ubicacion and that product already had units waiting in
its sin-ubicacion bucket, the alta counted the scanned qty as fresh units
and left the bucket untouched. The user wants the drain to be EXPLICIT
(MANUAL): a ProductCard checkbox decides whether drained units compose part
of the alta qty. 0 (default) preserves the historical pure-alta behavior
(单位 no bucket drain, no rescue audit row); > 0 triggers the rescue.

VALIDATION CONTRACT (the repository layer raises ``ValueError``):

  * ``drain_bucket_qty <= bucket_qty``      — the bucket must hold at
    least the requested drain (else stock_general would silently create
    units out of thin air inside the ubicacion). ValueError → 400.
  * ``drain_bucket_qty <= cantidad``        — the alta/ajuste declares the
    ubicacion's FINAL stock; you cannot ingest MORE bucket units into the
    ubicacion than the alta declares. ValueError → 400.

FLOW WHEN ``drain_bucket_qty > 0`` (the orchestrator's spec):

  1. Snapshot ``stock_general_anterior = get_producto_stock_total(producto)``
     AFTER Bug 1 fix — so it already includes the pre-drain bucket qty.
     Snapshot ``bucket_anterior_for_audit = bucket.get_cantidad(producto)``.
  2. Validate (both invariants above). Raise immediately if violated, BEFORE
     any mutation — the bucket must NOT be partly drained when the alta
     rejects the request.
  3. INSERT the ``rescate_sin_ubicacion`` audit row with conservation
     snapshots on ``stock_general`` (anterior = nuevo = sg_anterior — units
     moved BUCKET→physical, the user-visible total is unchanged by the move
     itself) AND the bucket-side snapshots
     (anterior = pre-drain bucket, nuevo = pre-drain − drain_bucket_qty).
  4. Call ``_bucket_repo.drain(...)`` inside the SAME ``BEGIN``/``commit``
     envelope (R1 deletes the row when cantidad hits 0).
  5. The alta main row is then INSERTed with
     ``stock_general_nuevo = sg_anterior + (stock_nuevo − stock_anterior) − drain_bucket_qty``
     (drained units conserve sg, so they do NOT count as a fresh increase).

COVERAGE
--------
- **B8.M1** — alta qty=25, drain=10, bucket=30 → U2.stock_actual=25,
  P.bucket=20, one rescate row qty=10 with bucket snapshots
  anterior=30, nuevo=20.
- **B8.M2** — alta qty=5, drain=0 (default), bucket=4 → NO rescate row,
  bucket unchanged (=4), U2.stock_actual=5.
- **B8.M3** — alta qty=5, drain=40, bucket=30 → ValueError raised; bucket
  UNCHANGED at 30 (drain aborted before mutation).
- **B8.M4** — alta qty=3, drain=5 (drain > cantidad) → ValueError raised.

Test pattern mirrors ``test_scanner_reassign_to_bucket.py`` (shared
estante_factory + distinct fila/columna, in-process repo calls). The
``_mov_repo.create_movimiento`` signature is the SCANNER's path (path #1)
— NOT the admin ``ubicacion_repository.assign_producto_to_ubicacion`` path.

Spec anchors: REQ-B-007, REQ-B-009, Slice 8 Bug 2 + Feature.
"""

from __future__ import annotations

import pytest

from app.repositories import movimiento_repository as _mov_repo
from app.repositories import stock_sin_ubicacion_repository as _bucket_repo


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test-scoped helpers
# ---------------------------------------------------------------------------


async def _fetch_all(db, sql, params):
    """Run ``sql`` with ``params``, return a list of ``dict`` (one per row)."""
    async with db.execute(sql, params) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def _scalar(db, sql, params):
    """Returns the first column of the first row as int; 0 on NULL/no-row."""
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


async def _arrange_p_q_at_u_with_bucket(
    db, estante_factory, producto_factory, ubicacion_factory,
    *,
    p_sku, estante_nombre, bucket_seed=30,
):
    """Run the common B8 arrange phase via direct: insert P + U1 (ubicacion
    is empty — the alta will be a *new* assignment, not a reassignment), then
    upsert the bucket with ``bucket_seed`` units for P.

    Returns ``(p, u1, estante_id)``. State after this returns:

      * ``ubicaciones[u1].producto_id``  = None  (fresh cell, awaiting alta)
      * ``ubicaciones[u1].stock_actual`` = 0
      * ``stock_sin_ubicacion[p]``        = bucket_seed (row EXISTS per R1)

    Test bodies then drive the scanner ``create_movimiento(tipo='alta', ...)``
    path with explicit ``drain_bucket_qty`` to exercise the Feature.
    """
    p = await producto_factory(sku=p_sku)
    estante_id = await estante_factory(nombre=estante_nombre)
    u1 = await ubicacion_factory(estante_id=estante_id, fila=1, columna=1)

    # Seed the bucket directly via the repo (NOT via an admin hand-action
    # that would itself write audit rows — we want a clean baseline audit
    # log so the test body can assert exclusively against ITS OWN alta row).
    # The bucket repo's `upsert_add` does NOT commit by design (the caller
    # owns the tx per the repo module's docstring); the test needs the write
    # durable so the subsequent `_create_movimiento_once`' `BEGIN` (line
    # 138 of `movimiento_repository.py`) can start cleanly. Committing
    # here mirrors what the conftest factories (estante/producto/ubicacion)
    # already do — close any implicit auto-begun transaction.
    await _bucket_repo.upsert_add(db, p, bucket_seed)
    await db.commit()
    return p, u1, estante_id


# ---------------------------------------------------------------------------
# B8.M1 — alta qty=25, drain=10, bucket=30 → U2.stock_actual=25,
# P.bucket=20, one rescate row qty=10 with bucket snapshots 30 → 20.
# ---------------------------------------------------------------------------


async def test_b8_m1_alta_with_drain_writes_rescate_row_and_drains_bucket(
    db_session, estante_factory, producto_factory, ubicacion_factory
):
    """The flag-bearer scenario from the user's slice 8 analysis. P holds
    bucket=30 (the seeded baseline). The operator enters an alta of 25
    onto U1 with the ``Utilizar unidades 'sin ubicación'`` checkbox checked
    AND ``drainAmount=10``. Expected post-tx state:

      * U1.producto_id == P, U1.stock_actual == 25 (qty taken from the alta
        + drained units; the alta's `cantidad` IS the final cell stock per
        the alta semantics, including the drained 10).
      * P.bucket == 20 (drained 10 from 30, per R1 still present since >0).
      * one ``rescate_sin_ubicacion`` row for P at U1 qty=10 with
        ``stock_sin_ubicacion_anterior=30`` and
        ``stock_sin_ubicacion_nuevo=20``.
      * the alta row records ``stock_general_anterior=30`` (sg-inclusive
        of bucket, the Bug 1 fix), ``stock_general_nuevo`` = 30 + (25 − 0)
        − 10 = 45 (conservation: 30 + 15 new units — the 10 drained units
        are conserved, NOT counted as new).
    """
    p, u1, _ = await _arrange_p_q_at_u_with_bucket(
        db_session, estante_factory, producto_factory, ubicacion_factory,
        p_sku="B8M1-P", estante_nombre="B8M1 Shelf", bucket_seed=30,
    )
    # Sanity: U1 holds nothing, P's bucket=30.
    ub = await _read_ub_row(db_session, u1)
    assert ub["producto_id"] is None
    assert ub["stock_actual"] == 0
    assert await _bucket_qty(db_session, p) == 30

    # Action: scanner alta P at U1 qty=25, drain=10.
    await _mov_repo.create_movimiento(
        db_session, usuario_id=None, producto_sku=p,
        ubicacion_id=u1, cantidad=25, tipo="alta",
        drain_bucket_qty=10,
    )

    # U1 now holds P at qty=25 (the alta's declared final stock; the 10
    # drained units AND 15 newly-counted units both reside at U1).
    ub = await _read_ub_row(db_session, u1)
    assert ub["producto_id"] == p
    assert ub["stock_actual"] == 25

    # Bucket drained by EXACTLY 10 (30 → 20). 20 > 0 → row still present
    # per R1 (NOT deleted).
    assert await _bucket_qty(db_session, p) == 20
    # R1 invariant: row present (not deleted on 20).
    assert await _scalar(
        db_session,
        "SELECT COUNT(*) FROM stock_sin_ubicacion WHERE producto_id = ?",
        (p,),
    ) == 1

    # Exactly ONE ``rescate_sin_ubicacion`` row for P at U1, qty=10, with
    # the bucket snapshots anterior=30 → nuevo=20.
    rows = await _fetch_all(
        db_session,
        "SELECT producto_id, ubicacion_id, cantidad, tipo, "
        "stock_general_anterior, stock_general_nuevo, "
        "stock_sin_ubicacion_anterior, stock_sin_ubicacion_nuevo "
        "FROM movimientos WHERE tipo = 'rescate_sin_ubicacion' "
        "AND producto_id = ?",
        (p,),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["producto_id"] == p
    assert row["ubicacion_id"] == u1
    assert row["cantidad"] == 10
    # Conservation on stock_general: the rescue MOVES 10 bucket units into
    # the ubicacion — the user-visible sg is unchanged by the move alone.
    assert row["stock_general_anterior"] == 30  # bucket-seeded pre-tx sg
    assert row["stock_general_nuevo"] == 30     # conservation
    # Bucket-side snapshots: pre-drain 30, post-drain 20.
    assert row["stock_sin_ubicacion_anterior"] == 30
    assert row["stock_sin_ubicacion_nuevo"] == 20

    # The alta row for P at U1: qty=25, stock_anterior=0, stock_nuevo=25.
    alta_rows = await _fetch_all(
        db_session,
        "SELECT cantidad, stock_anterior, stock_nuevo, "
        "stock_general_anterior, stock_general_nuevo, "
        "stock_sin_ubicacion_anterior, stock_sin_ubicacion_nuevo "
        "FROM movimientos WHERE tipo = 'alta' AND producto_id = ? "
        "AND ubicacion_id = ?",
        (p, u1),
    )
    assert len(alta_rows) == 1
    alta = alta_rows[0]
    assert alta["cantidad"] == 25
    assert alta["stock_anterior"] == 0
    assert alta["stock_nuevo"] == 25
    # sg snapshots per the orchestrator's formula:
    # anterior = 30 (Bug 1 fix includes pre-drain bucket)
    # nuevo    = 30 + (25 - 0) - 10 = 45 (drained units conserve sg)
    assert alta["stock_general_anterior"] == 30
    assert alta["stock_general_nuevo"] == 45
    # alta's bucket snapshots: NEW PRODUCT's bucket transition across
    # this tx (drain_qty=10): anterior=30, nuevo=20.
    assert alta["stock_sin_ubicacion_anterior"] == 30
    assert alta["stock_sin_ubicacion_nuevo"] == 20

    # Final invariant (REQ-B-009): user-visible sg(P) = physical(25) +
    # bucket(20) = 45.
    assert await _mov_repo.get_producto_stock_total(db_session, p) == 45


# ---------------------------------------------------------------------------
# B8.M2 — alta qty=5, drain=0 (default) → NO rescate row, bucket unchanged.
# This is the BACKWARDS-COMPAT regression lock — the default scanner flow
# (FE checkbox unchecked) must NOT change behavior compared to pre-Slice-8.
# ---------------------------------------------------------------------------


async def test_b8_m2_alta_with_zero_drain_is_a_pure_alta(
    db_session, estante_factory, producto_factory, ubicacion_factory
):
    """Default ``drain_bucket_qty=0`` (the FE's unchecked checkbox case)
    preserves the historical pure-alta path:

      * no ``rescate_sin_ubicacion`` row written,
      * bucket qty UNCHANGED,
      * U1.stock_actual = qty alta.

    This is the "the new Feature is opt-in — historical FE calls see only
    their own behavior shift on top of the Bug 1 fix" guarantee.
    """
    p, u1, _ = await _arrange_p_q_at_u_with_bucket(
        db_session, estante_factory, producto_factory, ubicacion_factory,
        p_sku="B8M2-P", estante_nombre="B8M2 Shelf", bucket_seed=4,
    )
    # Sanity: U1 empty, P.bucket=4.
    assert await _bucket_qty(db_session, p) == 4

    # Action: alta qty=5, drain=0 (the default; no Feature in play).
    await _mov_repo.create_movimiento(
        db_session, usuario_id=None, producto_sku=p,
        ubicacion_id=u1, cantidad=5, tipo="alta",
        drain_bucket_qty=0,
    )

    # U1 holds P at qty=5 (pure alta; no drain).
    ub = await _read_ub_row(db_session, u1)
    assert ub["producto_id"] == p
    assert ub["stock_actual"] == 5

    # Bucket UNCHANGED at 4 (zero-drain is a strict no-op on the bucket).
    assert await _bucket_qty(db_session, p) == 4

    # No rescate row written by this alta.
    rescate_count = await _scalar(
        db_session,
        "SELECT COUNT(*) FROM movimientos "
        "WHERE tipo = 'rescate_sin_ubicacion' AND producto_id = ?",
        (p,),
    )
    assert rescate_count == 0


# ---------------------------------------------------------------------------
# B8.M3 — alta qty=5, drain=40, bucket=30 → ValueError raised; bucket
# UNCHANGED at 30 (drain aborted BEFORE mutation).
# ---------------------------------------------------------------------------


async def test_b8_m3_drain_exceeds_bucket_raises_valueerror_and_keeps_bucket(
    db_session, estante_factory, producto_factory, ubicacion_factory
):
    """Rescate contract: ``drain_bucket_qty <= bucket_qty``. Asking for 40
    when the bucket only holds 30 raises ``ValueError`` BEFORE any
    mutation — the bucket stays at 30, the alta is NOT applied, and the
    route layer will translate this into HTTP 400. The test affirms the
    ``pytest.raises(ValueError)`` contract + the "diagnostic check before
    any data write" property (no half-mutated bucket cells)."""
    p, u1, _ = await _arrange_p_q_at_u_with_bucket(
        db_session, estante_factory, producto_factory, ubicacion_factory,
        p_sku="B8M3-P", estante_nombre="B8M3 Shelf", bucket_seed=30,
    )
    assert await _bucket_qty(db_session, p) == 30

    with pytest.raises(ValueError):
        await _mov_repo.create_movimiento(
            db_session, usuario_id=None, producto_sku=p,
            ubicacion_id=u1, cantidad=5, tipo="alta",
            drain_bucket_qty=40,
        )

    # Diagnostic-before-mutation contract: bucket UNCHANGED, no alta
    # row written, no rescate row written, U1 stays empty.
    assert await _bucket_qty(db_session, p) == 30
    ub = await _read_ub_row(db_session, u1)
    assert ub["producto_id"] is None
    assert ub["stock_actual"] == 0
    count_mov = await _scalar(
        db_session,
        "SELECT COUNT(*) FROM movimientos WHERE producto_id = ?",
        (p,),
    )
    assert count_mov == 0


# ---------------------------------------------------------------------------
# B8.M4 — alta qty=3, drain=5 (drain > cantidad) → ValueError raised.
# Cannot ingest MORE bucket units into the ubicacion than the alta declares
# (the alta's cantidad IS the ubicacion's final stock; a 3-declared with
# 5-drained would either lose 2 units or violate stock_general accounting).
# ---------------------------------------------------------------------------


async def test_b8_m4_drain_exceeds_cantidad_raises_valueerror(
    db_session, estante_factory, producto_factory, ubicacion_factory
):
    """Rescate contract: ``drain_bucket_qty <= cantidad``. Asking for drain=5
    when the user declared cantidad=3 is a logical inconsistency (the FE
    input ceiling is `min(bucketQty, cantidad)`, so this value should never
    reach the BE in practice — but the BE must enforce the contract too
    because the contract is what defends against a future FE regression)."""
    p, u1, _ = await _arrange_p_q_at_u_with_bucket(
        db_session, estante_factory, producto_factory, ubicacion_factory,
        p_sku="B8M4-P", estante_nombre="B8M4 Shelf", bucket_seed=10,
    )
    assert await _bucket_qty(db_session, p) == 10

    with pytest.raises(ValueError):
        await _mov_repo.create_movimiento(
            db_session, usuario_id=None, producto_sku=p,
            ubicacion_id=u1, cantidad=3, tipo="alta",
            drain_bucket_qty=5,
        )

    # Bucket UNCHANGED; U1 stays empty (no partial alta).
    assert await _bucket_qty(db_session, p) == 10
    ub = await _read_ub_row(db_session, u1)
    assert ub["producto_id"] is None
    assert ub["stock_actual"] == 0