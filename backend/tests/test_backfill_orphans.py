"""Tests for Slice 4 — Part D: backfill orphans (idempotent one-shot cleanup).

Covers the three scenarios D1, D2, D3 from spec #295 Part D for the
``backend/app/services/backfill_orphans.py`` standalone script.

Scenarios
---------
- **D1** — the DB has 4 orphan ubicaciones (``producto_id IS NULL`` and
  ``stock_actual > 0``) with quantities ``[10, 20, 5, 21]``. After
  ``await backfill_orphans.main(db_session)``:
    * 4 new ``movimientos`` rows of ``tipo='salvage_cleanup'`` are written;
    * each movimiento's ``cantidad`` matches the orphan's ``stock_actual``
      AND each movimiento's ``ubicacion_id`` matches the orphan's ``id``
      AND ``producto_id IS NULL`` (the orphan has no product by definition —
      REQ-D-002, REQ-D-003);
    * all 4 orphan ubicaciones are zeroed (``stock_actual = 0``).
  Anchors: REQ-D-001..007.

- **D2** — after a successful first run, a SECOND run finds zero orphans
  (every matching row has been zeroed), writes zero new ``movimientos``, and
  changes zero ``ubicaciones`` rows. The script returns ``0`` on the re-run.
  Anchors: REQ-D-001 (idempotency), REQ-D-002.

- **D3** — a ubicacion with ``producto_id IS NULL`` AND ``stock_actual = 0``
  is technically orphan-eligible by ``producto_id`` but has no stock to clean
  up. The orphan query's ``stock_actual > 0`` filter excludes it, so the
  script does NOT write a ``salvage_cleanup`` movimiento for it and does NOT
  touch its ``stock_actual`` row. This proves the inner-boundary guard inside
  the idempotency check (REQ-D-002): the script never produces an audit row
  for an already-empty orphan.

Carry-forward risk #3 (from Slice 2a's apply-progress): each test creates
ONE shared ``estante_id`` via :func:`estante_factory` (with a unique name to
avoid migration 014's partial unique index collision) and uses distinct
``(fila, columna)`` per :func:`ubicacion_factory` call —
``ubicaciones`` has ``UNIQUE (estante_id, fila, columna)`` AND
``qr_valor`` is UNIQUE across the whole table, so two factory calls sharing
the same cell or QR would raise IntegrityError at insert time.

Note: rows committed inside :func:`backfill_orphans.main` (via ``conn.commit()``)
persist within the per-test ``:memory:`` DB and are visible to subsequent
SELECTs in the SAME test. Per-test isolation holds because the ``db_session``
fixture destroys the ``:memory:`` DB at teardown (``rollback()`` + ``close()``)
per the conftest docstring — no test bleeds state into another.

Pre-existing "Suelto" ubicacion (seeded by migration 004 with
``producto_id IS NULL, stock_actual = 0``) is ALWAYS present in the in-memory
DB. It matches ``WHERE producto_id IS NULL`` but is excluded from the actual
backfill by the ``stock_actual > 0`` filter — it's a physical surface for
"Suelto / loose" stock, NOT an orphan. The tests therefore track explicit
``orphan_id`` lists and select by ID for jejich sanity comparisons, instead of
by the loose-predicate ``WHERE producto_id IS NULL`` (which would catch the
Suelto row and inflate counts by 1).

Spec anchors: REQ-D-001..007, REQ-X-006, REQ-X-007.
"""

from __future__ import annotations

import pytest

from app.services import backfill_orphans


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Small test-scoped async query helpers (NOT fixtures — just inline reads to
# keep the assertions readable and the scenarios self-contained).
# ---------------------------------------------------------------------------


async def _count_salvage_cleanup(conn) -> int:
    """Count ``salvage_cleanup`` movimientos currently in the DB."""
    async with conn.execute(
        "SELECT COUNT(*) FROM movimientos WHERE tipo = 'salvage_cleanup'"
    ) as cur:
        row = await cur.fetchone()
    return int(row[0])


async def _stock_actual_by_id(conn, ub_id: int) -> int:
    """Read ``stock_actual`` for a specific ubicacion by ``id``."""
    async with conn.execute(
        "SELECT stock_actual FROM ubicaciones WHERE id = ?",
        (ub_id,),
    ) as cur:
        row = await cur.fetchone()
    assert row is not None, f"ubicacion id={ub_id} disappeared from DB"
    return int(row[0])


async def _fetch_movimientos_for_ubicaciones(
    conn, ub_ids: list[int]
) -> list[dict]:
    """Return ``salvage_cleanup`` movimientos whose ``ubicacion_id`` is in
    ``ub_ids``, ordered by ``id`` for stable comparisons.
    """
    if not ub_ids:
        return []
    placeholders = ",".join("?" * len(ub_ids))
    async with conn.execute(
        f"SELECT id, ubicacion_id, cantidad, producto_id FROM movimientos "
        f"WHERE tipo = 'salvage_cleanup' AND ubicacion_id IN ({placeholders}) "
        f"ORDER BY id",
        tuple(ub_ids),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def _suelto_ubicacion(conn) -> dict | None:
    """Return the pre-existing Suelto ubicacion row (``qr_valor='Suelto'``)
    if present, else ``None``. Used to assert Suelto is UNCHANGED by backfill.
    """
    async with conn.execute(
        "SELECT id, producto_id, stock_actual, qr_valor FROM ubicaciones "
        "WHERE qr_valor = 'Suelto'"
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# D1 — backfill 4 orphans with qtys [10, 20, 5, 21] (REQ-D-001..007)
# ---------------------------------------------------------------------------


class TestBackfillOrphansScenarios:
    """The 3 spec scenarios for ``backfill_orphans.main`` (D1, D2, D3)."""

    async def test_d1_backfill_4_orphans(
        self,
        db_session,
        estante_factory,
        ubicacion_factory,
    ):
        # GIVEN the DB has 4 orphans with stock_actual [10, 20, 5, 21]
        estante_id = await estante_factory(nombre="D1 Shelf")
        qtys = [10, 20, 5, 21]
        orphan_ids: list[int] = []
        for idx, qty in enumerate(qtys, start=1):
            ub_id = await ubicacion_factory(
                estante_id=estante_id,
                fila=idx,
                columna=1,
                producto_id=None,
                stock_actual=qty,
            )
            orphan_ids.append(ub_id)

        # Pre-backfill sanity: zero salvage_cleanup rows in the DB, each
        # freshly-seeded orphan has the stock_actual we set. (Tracked by ID
        # rather than by the orphan predicate — see the Suelto note in the
        # module docstring.)
        assert await _count_salvage_cleanup(db_session) == 0
        for idx, ub_id in enumerate(orphan_ids):
            assert await _stock_actual_by_id(db_session, ub_id) == qtys[idx]

        # Capture the pre-existing Suelto ubicacion (seeded by migration 004
        # with producto_id IS NULL, stock_actual = 0). It is NOT an orphan;
        # the backfill MUST leave it completely untouched.
        suelto_before = await _suelto_ubicacion(db_session)
        assert suelto_before is not None, "Suelto ubicacion should be seeded"
        assert suelto_before["stock_actual"] == 0
        assert suelto_before["producto_id"] is None

        # WHEN backfill runs
        n_backfilled = await backfill_orphans.main(db_session)

        # THEN 4 orphans were backfilled
        assert n_backfilled == 4

        # AND 4 salvage_cleanup movimientos were written
        mov_count = await _count_salvage_cleanup(db_session)
        assert mov_count == 4

        # AND each movimiento has qty matching the orphan's stock_actual AND
        # ubicacion_id matching the orphan's id AND producto_id IS NULL.
        mov_rows = await _fetch_movimientos_for_ubicaciones(db_session, orphan_ids)
        assert len(mov_rows) == 4
        by_ubicacion = {r["ubicacion_id"]: r for r in mov_rows}
        assert set(by_ubicacion.keys()) == set(orphan_ids)
        for idx, ub_id in enumerate(orphan_ids):
            mov = by_ubicacion[ub_id]
            assert mov["cantidad"] == qtys[idx], (
                f"movimiento for ubicacion {ub_id} expected qty={qtys[idx]} "
                f"got {mov['cantidad']}"
            )
            assert mov["producto_id"] is None, (
                f"movimiento for orphan ubicacion {ub_id} must have "
                f"producto_id IS NULL (REQ-D-002/003)"
            )

        # AND all 4 orphan ubicaciones now have stock_actual = 0
        for ub_id in orphan_ids:
            assert await _stock_actual_by_id(db_session, ub_id) == 0, (
                f"orphan ubicacion {ub_id} must be zeroed after backfill"
            )

        # AND the Suelto ubicacion was NOT touched by backfill (it has
        # stock_actual=0 already → excluded by the stock_actual > 0 filter).
        suelto_after = await _suelto_ubicacion(db_session)
        assert suelto_after["stock_actual"] == suelto_before["stock_actual"]
        assert suelto_after["producto_id"] == suelto_before["producto_id"]
        assert suelto_after["qr_valor"] == "Suelto"


    # -----------------------------------------------------------------------
    # D2 — idempotent second run: 0 new movimientos, 0 ubicaciones changed
    # -----------------------------------------------------------------------

    async def test_d2_idempotent_second_run(
        self,
        db_session,
        estante_factory,
        ubicacion_factory,
    ):
        # GIVEN the DB has 4 orphans (qtys 10, 20, 30, 40 — distinct from
        # D1's [10, 20, 5, 21] so a cross-test regression is obvious). Track
        # IDs explicitly so the second-run idempotency asserts compare with
        # THOSE orphans, not the pre-existing Suelto match-by-predicate.
        estante_id = await estante_factory(nombre="D2 Shelf")
        seeded_qtys = [10, 20, 30, 40]
        orphan_ids: list[int] = []
        for idx, qty in enumerate(seeded_qtys, start=1):
            ub_id = await ubicacion_factory(
                estante_id=estante_id,
                fila=idx,
                columna=1,
                producto_id=None,
                stock_actual=qty,
            )
            orphan_ids.append(ub_id)

        # WHEN backfill runs the FIRST time
        n1 = await backfill_orphans.main(db_session)
        assert n1 == 4, "first run backfills all 4 orphans"
        mov_count_after_first = await _count_salvage_cleanup(db_session)
        assert mov_count_after_first == 4

        # Verify first run actually zeroed each orphan AND eliminated all
        # non-zero orphans (the stock_actual > 0 filter sweeps only the rows
        # the script will see on the NEXT run).
        for ub_id in orphan_ids:
            assert await _stock_actual_by_id(db_session, ub_id) == 0

        # AND WHEN backfill runs AGAIN (idempotency check — REQ-D-001)
        n2 = await backfill_orphans.main(db_session)

        # THEN the second run backfills 0 orphans (orphan query returns 0
        # rows because every qualifying row was zeroed on the first run).
        assert n2 == 0, (
            "idempotent second run must report 0 backfilled orphans"
        )

        # AND no new movimientos were written (count unchanged).
        mov_count_after_second = await _count_salvage_cleanup(db_session)
        assert mov_count_after_second == mov_count_after_first, (
            "idempotency violation: movimientos count changed on second run"
        )

        # AND no ubicaciones row was changed by the second run — every
        # orphan remains at 0 from the first run.
        for ub_id in orphan_ids:
            assert await _stock_actual_by_id(db_session, ub_id) == 0, (
                f"idempotency violation: ubicacion {ub_id} changed on second run"
            )

        # AND the Suelto ubicacion stayed at stock_actual=0 + producto_id=NULL
        # across BOTH runs (never an orphan, never modified).
        suelto_after = await _suelto_ubicacion(db_session)
        assert suelto_after is not None
        assert int(suelto_after["stock_actual"]) == 0
        assert suelto_after["producto_id"] is None


    # -----------------------------------------------------------------------
    # D3 — orphan-eligible (producto_id IS NULL) but stock_actual = 0 boundary
    # -----------------------------------------------------------------------

    async def test_d3_orphan_zero_stock_boundary(
        self,
        db_session,
        estante_factory,
        ubicacion_factory,
    ):
        # GIVEN a ubicacion with producto_id IS NULL AND stock_actual = 0
        # (orphan-eligible by producto_id, but with no stock to clean up)
        estante_id = await estante_factory(nombre="D3 Shelf")
        ub_id = await ubicacion_factory(
            estante_id=estante_id,
            fila=1,
            columna=1,
            producto_id=None,
            stock_actual=0,
        )

        # Sanity: the row exists, it's just an empty orphan.
        assert await _count_salvage_cleanup(db_session) == 0

        # WHEN backfill runs
        n_backfilled = await backfill_orphans.main(db_session)

        # THEN it reports 0 backfilled orphans (the stock_actual > 0 filter
        # excluded this row — REQ-D-002 inner boundary).
        assert n_backfilled == 0, (
            "empty orphan (stock_actual=0) must not be counted as backfilled"
        )

        # AND no salvage_cleanup movimiento was written for it
        assert await _count_salvage_cleanup(db_session) == 0, (
            "no audit row should be written for an empty orphan"
        )

        # AND the ubicacion row itself is untouched (still stock_actual=0,
        # still producto_id=NULL — bare no-op).
        async with db_session.execute(
            "SELECT stock_actual, producto_id FROM ubicaciones WHERE id = ?",
            (ub_id,),
        ) as cur:
            row = await cur.fetchone()
        assert int(row["stock_actual"]) == 0
        assert row["producto_id"] is None