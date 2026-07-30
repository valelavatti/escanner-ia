"""Tests for Slice 8 Bug 1 fix — ``get_producto_stock_total`` now INCLUDES
the ``stock_sin_ubicacion`` bucket qty in its returned sum (was PHYSICAL +
Suelto only before Slice 8).

WHY THIS FIX
------------
The user's Bug 1 report: scanning an alta of 25 onto a new ubicacion when the
product already had 30 units sitting in the bucket showed
"Stock general: 0 → 25" on the historial. The displayed diagonal lied — the
product really owned 30 (bucket) + 25 (new physical) = 55 units, but the
snapshot captured only the physical+Suelto portion (= 0 + 25 = 25).

Slice 8 Bug 1 fix: ``get_producto_stock_total`` now adds the bucket qty on
its own, so every consumer (the snapshot helper inside
``_create_movimiento_once``, the explicit desasignacion/asignacion helpers,
the rescue helper, AND the ``GET /productos/{codigo_de_barra}/stock-total``
endpoint) sees the truthful 3-stock total. The endpoint ``productos.py``
was edited in the same slice to STOP double-adding the bucket on top of
this function (the previous ``physical + bucket`` formula would now
double-count).

COVERAGE
--------
- T1 — fisico=5 + bucket=10 → 15
- T2 — no ubicacion + bucket=8   → 8
- T3 — fisico=5 + bucket absent  → 5
- T4 — migration 017 preserves every pre-existing ``movimientos`` row across
  the table-rebuild (DEFAULT 0 on the two new ``stock_sin_ubicacion_*``
  columns; no row lost).

T4 uses a STANDALONE in-memory connection (not the ``db_session`` fixture)
so the test can apply migrations 001..016 only, insert N audit rows, then
run migration 017 and verify the row count and the new-column DEFAULT 0
invariant. This is the "insert-before/check" pattern the SQLite expert
skill mandates for table-rebuild migrations.

Spec anchors: REQ-B-009, Slice 8 Bug 1 + Feature (migration 017).
"""

from __future__ import annotations

import aiosqlite
import pytest
import pytest_asyncio

from app.core.database import configure_connection
from app.core.migrations import MIGRATIONS, run_migrations
from app.repositories import movimiento_repository as _mov_repo
from app.repositories import stock_sin_ubicacion_repository as _bucket_repo


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# T1 — fisico=5 + bucket=10 → get_producto_stock_total == 15
# ---------------------------------------------------------------------------


async def test_t1_fisico_plus_bucket_sums_to_15(
    db_session, estante_factory, producto_factory, ubicacion_factory
):
    """P with 5 units on a physical cell + 10 units in the sin-ubicacion
    bucket reports a stock_total of 15 — the user-visible invariant
    REQ-B-009. Pre-Slice-8 this returned 5 (PHYSICAL-only); with Bug 1 fix
    the bucket is internalized."""
    p = await producto_factory(sku="T1-P", codigo_de_barra="BAR-T1")
    estante_id = await estante_factory(nombre="T1 Shelf")
    await ubicacion_factory(
        estante_id=estante_id, fila=1, columna=1,
        producto_id=p, stock_actual=5,
    )
    await _bucket_repo.upsert_add(db_session, p, 10)

    total = await _mov_repo.get_producto_stock_total(db_session, p)
    assert total == 15


# ---------------------------------------------------------------------------
# T2 — no ubicacion + bucket=8 → returns 8
# ---------------------------------------------------------------------------


async def test_t2_only_bucket_returns_8(db_session, producto_factory):
    """P whose units live ONLY in the bucket (no ubicaciones row, no Suelto
    movimientos) reports its bucket qty. Pre-Slice-8 this returned 0 —
    the diagonal undercounted the user-visible stock by the bucket amount;
    the Bug 1 fix surfaces the bucket here too."""
    p = await producto_factory(sku="T2-P", codigo_de_barra="BAR-T2")
    await _bucket_repo.upsert_add(db_session, p, 8)

    total = await _mov_repo.get_producto_stock_total(db_session, p)
    assert total == 8


# ---------------------------------------------------------------------------
# T3 — fisico=5 + bucket absent → returns 5
# ---------------------------------------------------------------------------


async def test_t3_only_physical_returns_5(
    db_session, estante_factory, producto_factory, ubicacion_factory
):
    """P whose units ALL sit on a physical cell + no bucket row (R1
    invariant: a missing row == 0 units) reports exactly the physical
    qty — guaranteeing this fix is ADDITIVE (it does not double-count
    when bucket is absent). """
    p = await producto_factory(sku="T3-P", codigo_de_barra="BAR-T3")
    estante_id = await estante_factory(nombre="T3 Shelf")
    await ubicacion_factory(
        estante_id=estante_id, fila=1, columna=1,
        producto_id=p, stock_actual=5,
    )

    total = await _mov_repo.get_producto_stock_total(db_session, p)
    assert total == 5


# ---------------------------------------------------------------------------
# T4 — migration 017 preserves every pre-existing ``movimientos`` row across
# the table-rebuild and fills the two new ``stock_sin_ubicacion_*`` columns
# with DEFAULT 0. (SQLite cannot ALTER ADD NOT NULL safely; the table-rebuild
# idiom inserts every historical row with an explicit column list that
# OMITS the new columns, so SQLite applies DEFAULT 0 for them. This test
# proves it.)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t4_migration_017_preserves_existing_rows():
    """Apply migrations 001..016 to a STANDALONE in-memory DB (NOT the
    fixture-backed ``db_session`` which already runs 017), insert 3 movimiento
    rows, then run migration 017 (the table-rebuild) and confirm:

      * row count unchanged (3),
      * every preserved row's ``stock_sin_ubicacion_anterior`` and
        ``stock_sin_ubicacion_nuevo`` are exactly 0 (the DEFAULT 0 from
        migration 017's INSERT ... SELECT with the explicit column list
        omitting the two new columns).

    This is the SQLite skill's "insert-before/check" pattern for table
    rebuild migrations: DO NOT rely on the migration's SQL alone — verify
    against real inserted rows.
    """
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await configure_connection(conn)

    try:
        # Stage 1: apply every migration EXCEPT 017 (the new columns).
        up_to_016 = [
            (version, name, sql)
            for version, name, sql in MIGRATIONS
            if version <= 16
        ]
        # Manually mimic the ``run_migrations`` loop for the subset
        # (``run_migrations`` always drains the full ``MIGRATIONS`` list,
        # so we replicate the bookkeeping inline to gate at 016).
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await conn.commit()
        for version, name, sql in up_to_016:
            await conn.executescript(sql)
            await conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (version, name),
            )
            await conn.commit()

        # Stage 2: insert 3 audit rows pre-017. Minimal legit row (per the 001
        # schema + migration 008's stock_general columns) — using a real
        # ubicacion so the FK passes. Suelto estante is auto-seeded by
        # migration 004; reuse ubicacion_id=1 for the rows.
        # (We bypass movimiento_repository helpers and write raw INSERTs to
        # exactly simulate a historical audit log from BEFORE any Slice 8
        # tooling existed.)
        for qty in (10, 25, 0):
            await conn.execute(
                """
                INSERT INTO movimientos
                    (usuario_id, producto_id, ubicacion_id, cantidad,
                     stock_anterior, stock_nuevo, timestamp, tipo,
                     stock_general_anterior, stock_general_nuevo)
                VALUES (NULL, NULL, 1, ?, ?, ?, CURRENT_TIMESTAMP, 'alta', 0, 0)
                """,
                (qty, 0, qty),
            )
        await conn.commit()

        pre_count_row = await conn.execute(
            "SELECT COUNT(*) FROM movimientos"
        )
        pre_count = (await pre_count_row.fetchone())[0]
        assert pre_count == 3, "pre-017 row count expectation"

        # Stage 3: run migration 017 via the standard ``run_migrations``
        # entry (it skips already-applied versions 1..16 and applies 17
        # ONLY). Idempotency contract holds.
        await run_migrations(conn)

        post_count_row = await conn.execute(
            "SELECT COUNT(*) FROM movimientos"
        )
        post_count = (await post_count_row.fetchone())[0]
        assert post_count == 3, "migration 017 must NOT lose any row"

        # Check constraint preserved: insert a 'rescate_sin_ubicacion' row
        # (added by 016, NOT NULL DEFAULT 0 columns are the Slice 8 new ones).
        # Verifies migration 017 replicated migration 016's CHECK extension
        # (the 6 literals the orchestrator enumerated)
        # — without that CHECK replication this INSERT would fail.
        await conn.execute(
            """
            INSERT INTO movimientos
                (usuario_id, producto_id, ubicacion_id, cantidad,
                 stock_anterior, stock_nuevo, timestamp, tipo,
                 stock_general_anterior, stock_general_nuevo,
                 stock_sin_ubicacion_anterior, stock_sin_ubicacion_nuevo)
            VALUES (NULL, NULL, 1, 5, 0, 5,
                    CURRENT_TIMESTAMP, 'rescate_sin_ubicacion', 0, 0, 10, 5)
            """
        )
        await conn.commit()

        post_insert_count_row = await conn.execute(
            "SELECT COUNT(*) FROM movimientos"
        )
        post_insert_count = (await post_insert_count_row.fetchone())[0]
        assert post_insert_count == 4, "CHECK on `movimientos.tipo` accepts 'rescate_sin_ubicacion' post-017"

        # Stage 4: the 3 PRE-017 rows must show DEFAULT 0 on the two new
        # columns (the historic-shape acceptance per migration 017's design).
        legacy_rows = await conn.execute(
            """
            SELECT id, stock_sin_ubicacion_anterior, stock_sin_ubicacion_nuevo
            FROM movimientos
            WHERE tipo = 'alta'
            ORDER BY id ASC
            """
        )
        legacies = await legacy_rows.fetchall()
        assert len(legacies) == 3
        for row in legacies:
            assert dict(row)["stock_sin_ubicacion_anterior"] == 0
            assert dict(row)["stock_sin_ubicacion_nuevo"] == 0
    finally:
        try:
            await conn.rollback()
        except aiosqlite.Error:
            pass
        await conn.close()