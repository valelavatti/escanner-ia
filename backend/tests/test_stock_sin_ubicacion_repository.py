"""Tests for :mod:`app.repositories.stock_sin_ubicacion_repository` (Slice 2a).

Covers the bucket data layer introduced by migration 015:

- ``get_cantidad``   — returns 0 by default (no row) and reads stored rows.
- ``upsert_add``     — fresh-row insert, accumulating on an existing row,
                      and the qty=0 no-op invariant (no zero-row is ever
                      created — R1).
- ``drain``          — under-drain partial (bucket has MORE than requested,
                      row kept), exact drain (bucket == requested → row
                      deleted by R1), over-drain (bucket < requested → drained
                      == bucket, row deleted by R1), and no-row drain.
- ``delete_if_zero`` — defensive deletion of an artificially-inserted zero
                      row, no-op on a positive row, no-op on missing row.

Every test owns its own in-memory DB (per-test clean-room ``db_session``
fixture from ``conftest.py``) so bucket state never leaks between tests.

Spec anchors: REQ-B-002, REQ-B-005, REQ-B-006, REQ-B-007, R1, REQ-X-006.
"""

from __future__ import annotations

import pytest

from app.repositories import stock_sin_ubicacion_repository as bucket


pytestmark = pytest.mark.asyncio


class TestStockSinUbicacionRepository:
    """Scenario coverage for the sin-ubicacion bucket data layer."""

    # ------------------------------------------------------------------ #
    # get_cantidad                                                        #
    # ------------------------------------------------------------------ #

    async def test_get_cantidad_returns_zero_when_no_row(self, db_session, producto_factory):
        sku = await producto_factory(sku="PROD-A")
        qty = await bucket.get_cantidad(db_session, sku)
        assert qty == 0

    async def test_get_cantidad_returns_stored_value(self, db_session, producto_factory):
        sku = await producto_factory(sku="PROD-A")
        # Use raw SQL here (this test pre-dates / pre-supposes the helper)
        # so the helper's read path is independent of its own write path.
        await db_session.execute(
            "INSERT INTO stock_sin_ubicacion (producto_id, cantidad) VALUES (?, ?)",
            (sku, 7),
        )
        await db_session.commit()
        assert await bucket.get_cantidad(db_session, sku) == 7

    # ------------------------------------------------------------------ #
    # upsert_add                                                          #
    # ------------------------------------------------------------------ #

    async def test_upsert_add_creates_row_with_qty(self, db_session, producto_factory):
        sku = await producto_factory(sku="PROD-A")
        new_qty = await bucket.upsert_add(db_session, sku, 5)
        await db_session.commit()
        assert new_qty == 5
        assert await bucket.get_cantidad(db_session, sku) == 5

    async def test_upsert_add_accumulates_on_existing_row(self, db_session, producto_factory):
        sku = await producto_factory(sku="PROD-A")
        await bucket.upsert_add(db_session, sku, 5)
        new_qty = await bucket.upsert_add(db_session, sku, 3)
        await db_session.commit()
        assert new_qty == 8
        assert await bucket.get_cantidad(db_session, sku) == 8

    async def test_upsert_add_with_zero_qty_is_no_op_and_creates_no_row(
        self, db_session, producto_factory
    ):
        """R1 guard: upsert_add with qty=0 must NOT create a zero-cantidad
        row. A row in this table ALWAYS means qty > 0 (R1 invariant)."""
        sku = await producto_factory(sku="PROD-A")
        new_qty = await bucket.upsert_add(db_session, sku, 0)
        await db_session.commit()
        assert new_qty == 0  # surface contract: caller sees "no change"
        # And no row was inserted (R1 — missing row IS the zero state).
        async with db_session.execute(
            "SELECT COUNT(*) FROM stock_sin_ubicacion WHERE producto_id = ?",
            (sku,),
        ) as cursor:
            count_row = await cursor.fetchone()
        assert count_row[0] == 0

    async def test_upsert_add_with_zero_qty_leaves_existing_row_intact(
        self, db_session, producto_factory
    ):
        """A second upsert_add(qty=0) on an existing positive row must not
        delete or alter the row."""
        sku = await producto_factory(sku="PROD-A")
        await bucket.upsert_add(db_session, sku, 5)
        new_qty = await bucket.upsert_add(db_session, sku, 0)
        await db_session.commit()
        assert new_qty == 5
        assert await bucket.get_cantidad(db_session, sku) == 5

    async def test_upsert_add_negative_qty_raises(self, db_session, producto_factory):
        """Gristle: a negative add is a programming error, not a 0-bucket
        state. Reject loudly so callers don't smuggle a negative through
        and silently corrupt accounting."""
        sku = await producto_factory(sku="PROD-A")
        with pytest.raises(ValueError):
            await bucket.upsert_add(db_session, sku, -1)

    # ------------------------------------------------------------------ #
    # drain                                                               #
    # ------------------------------------------------------------------ #

    async def test_drain_with_no_row_returns_zero_and_inserts_nothing(
        self, db_session, producto_factory
    ):
        """Draining from an empty bucket (R1: missing row == 0 units) is a
        safe no-op: drained == 0, no row inserted."""
        sku = await producto_factory(sku="PROD-A")
        drained = await bucket.drain(db_session, sku, 5)
        await db_session.commit()
        assert drained == 0
        async with db_session.execute(
            "SELECT COUNT(*) FROM stock_sin_ubicacion WHERE producto_id = ?",
            (sku,),
        ) as cursor:
            count_row = await cursor.fetchone()
        assert count_row[0] == 0

    async def test_drain_partial_keeps_remaining_row(self, db_session, producto_factory):
        """bucket=10, drain 4 → row STAYS at cantidad=6 (R1: row kept when
        qty > 0)."""
        sku = await producto_factory(sku="PROD-A")
        await bucket.upsert_add(db_session, sku, 10)
        drained = await bucket.drain(db_session, sku, 4)
        await db_session.commit()
        assert drained == 4
        assert await bucket.get_cantidad(db_session, sku) == 6

    async def test_drain_exactly_to_zero_deletes_row(self, db_session, producto_factory):
        """bucket=5, drain 5 → row DELETED (R1: DELETE-row-on-zero).
        get_cantidad returns 0 after because there is no row, not because
        there is a zero-row."""
        sku = await producto_factory(sku="PROD-A")
        await bucket.upsert_add(db_session, sku, 5)
        drained = await bucket.drain(db_session, sku, 5)
        await db_session.commit()
        assert drained == 5
        async with db_session.execute(
            "SELECT COUNT(*) FROM stock_sin_ubicacion WHERE producto_id = ?",
            (sku,),
        ) as cursor:
            count_row = await cursor.fetchone()
        assert count_row[0] == 0
        # And read-back via the helper is also 0 (R1 is observably upheld).
        assert await bucket.get_cantidad(db_session, sku) == 0

    async def test_drain_over_capacity_drains_only_available_and_deletes_row(
        self, db_session, producto_factory
    ):
        """bucket=3, drain 10 → drained == 3 (NOT 10) — drain is capped at
        available. R1: row deleted because cantidad reached 0."""
        sku = await producto_factory(sku="PROD-A")
        await bucket.upsert_add(db_session, sku, 3)
        drained = await bucket.drain(db_session, sku, 10)
        await db_session.commit()
        assert drained == 3
        async with db_session.execute(
            "SELECT COUNT(*) FROM stock_sin_ubicacion WHERE producto_id = ?",
            (sku,),
        ) as cursor:
            count_row = await cursor.fetchone()
        assert count_row[0] == 0

    async def test_drain_zero_requested_returns_zero_no_mutation(
        self, db_session, producto_factory
    ):
        """Draining 0 units from a positive bucket must not change the row
        (drained == 0, row stays positive)."""
        sku = await producto_factory(sku="PROD-A")
        await bucket.upsert_add(db_session, sku, 4)
        drained = await bucket.drain(db_session, sku, 0)
        await db_session.commit()
        assert drained == 0
        assert await bucket.get_cantidad(db_session, sku) == 4

    async def test_drain_negative_requested_raises(self, db_session, producto_factory):
        """Draining a negative quantity is a programming error — reject."""
        sku = await producto_factory(sku="PROD-A")
        await bucket.upsert_add(db_session, sku, 4)
        with pytest.raises(ValueError):
            await bucket.drain(db_session, sku, -1)

    # ------------------------------------------------------------------ #
    # delete_if_zero (defensive backstop for R1)                          #
    # ------------------------------------------------------------------ #

    async def test_delete_if_zero_noop_when_no_row(self, db_session, producto_factory):
        sku = await producto_factory(sku="PROD-A")
        await bucket.delete_if_zero(db_session, sku)
        await db_session.commit()
        assert await bucket.get_cantidad(db_session, sku) == 0

    async def test_delete_if_zero_noop_when_qty_positive(self, db_session, producto_factory):
        """delete_if_zero must NOT remove a positive row (only zero rows
        qualify for R1 cleanup)."""
        sku = await producto_factory(sku="PROD-A")
        await bucket.upsert_add(db_session, sku, 5)
        await bucket.delete_if_zero(db_session, sku)
        await db_session.commit()
        assert await bucket.get_cantidad(db_session, sku) == 5

    async def test_delete_if_zero_removes_artificially_inserted_zero_row(
        self, db_session, producto_factory
    ):
        """A zero-row should never legitimately exist (R1 invariant), but
        if one does (e.g. legacy data, manual SQL), delete_if_zero must
        clean it up so the presence predicate regains its meaning."""
        sku = await producto_factory(sku="PROD-A")
        # Bypass the helper to artificially violate R1.
        await db_session.execute(
            "INSERT INTO stock_sin_ubicacion (producto_id, cantidad) VALUES (?, 0)",
            (sku,),
        )
        await db_session.commit()
        await bucket.delete_if_zero(db_session, sku)
        await db_session.commit()
        async with db_session.execute(
            "SELECT COUNT(*) FROM stock_sin_ubicacion WHERE producto_id = ?",
            (sku,),
        ) as cursor:
            count_row = await cursor.fetchone()
        assert count_row[0] == 0