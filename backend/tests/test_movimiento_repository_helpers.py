"""Tests for the two new ``movimiento_repository`` helpers added in Slice 2a:

- :func:`movimiento_repository.create_movimiento_rescate_sin_ubicacion`
  (tipo = ``'rescate_sin_ubicacion'``)
- :func:`movimiento_repository.create_movimiento_salvage_cleanup`
  (tipo = ``'salvage_cleanup'``, ``producto_id = NULL`` by design — REQ-D-002)

Coverage map:

- L1 — rescate inserts a row with the new tipo literal (proves migration 016
  extended the CHECK constraint to accept ``'rescate_sin_ubicacion'`` — pre-016
  this insert would have been rejected by SQLite).
- L2 — rescate records qty in ``cantidad``, snapshots per-ubicacion
  ``stock_anterior=0`` / ``stock_nuevo=qty``.
- L3 — rescate computes ``stock_general_anterior`` lazily from
  ``get_producto_stock_total``; with no prior stock, anterior=0 and
  nuevo=qty (bucket qty was NOT counted pre-rescue; moving it OUT of the
  bucket INTO a ubicacion increases stock_general by exactly qty).
- L4 — rescate with existing prior stock at another ubicacion: anterior=existing
  sum, nuevo=existing+qty (preserves the lazy-snapshot contract).
- L5 — rescate with ``usuario_id=None`` works (movimientos.usuario_id nullable
  per migration 012).
- L6 — salvage inserts a row with the new tipo literal AND ``producto_id IS
  NULL`` (proves migration 016 extended CHECK AND proves migration 001's
  nullable ``producto_id`` column accepts NULL).
- L7 — salvage records qty as ``cantidad``, ``stock_anterior=qty``, ``stock_nuevo=0``
  (ubicacion zeroed in the same tx).
- L8 — salvage records ``stock_general_anterior=0`` and ``stock_general_nuevo=0``
  (orphan has no product).
- L9 — salvage with ``usuario_id=None`` works.
- L10 (regression gate) — every original tipo literal ('alta', 'ajuste',
  'asignacion', 'desasignacion') is STILL accepted after migration 016's
  table-rebuild (proves the rebuild preserved the 4 original literals).

Spec anchors: REQ-B-006, REQ-B-007, REQ-D-002, REQ-D-003, REQ-X-006.
"""

from __future__ import annotations

import pytest

from app.repositories import movimiento_repository as repo


pytestmark = pytest.mark.asyncio


class TestMovimientoRescateSinUbicacion:
    """``create_movimiento_rescate_sin_ubicacion`` — Slice 2a additions."""

    async def test_inserts_row_with_new_tipo_literal(
        self, db_session, producto_factory, ubicacion_factory
    ):
        """Migration 016 must extend ``movimientos.tipo`` CHECK to accept
        ``'rescate_sin_ubicacion'``. Pre-016 this INSERT would have raised
        ``sqlite3.IntegrityError`` (CHECK constraint failed). This test
        proves the migration landed AND the helper compiles valid SQL."""
        sku = await producto_factory(sku="PROD-R")
        ub_id = await ubicacion_factory()
        mov_id = await repo.create_movimiento_rescate_sin_ubicacion(
            db_session, sku, ub_id, qty=5
        )
        await db_session.commit()

        async with db_session.execute(
            "SELECT tipo, producto_id, ubicacion_id, cantidad, "
            "stock_anterior, stock_nuevo "
            "FROM movimientos WHERE id = ?",
            (mov_id,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
        assert row["tipo"] == "rescate_sin_ubicacion"
        assert row["producto_id"] == sku
        assert row["ubicacion_id"] == ub_id
        assert row["cantidad"] == 5
        assert row["stock_anterior"] == 0
        assert row["stock_nuevo"] == 5

    async def test_stock_general_nuevo_increases_by_qty_with_no_prior_stock(
        self, db_session, producto_factory, ubicacion_factory
    ):
        """With NO prior ubicaciones for the product, ``stock_general_anterior``
        is 0 (bucket qty was NOT counted in stock_general pre-rescue — see
        the 3-stock concept). After rescuing ``qty`` units into an empty
        ubicacion, ``stock_general_nuevo = qty``."""
        sku = await producto_factory(sku="PROD-R2")
        ub_id = await ubicacion_factory()
        mov_id = await repo.create_movimiento_rescate_sin_ubicacion(
            db_session, sku, ub_id, qty=5
        )
        await db_session.commit()
        async with db_session.execute(
            "SELECT stock_general_anterior, stock_general_nuevo "
            "FROM movimientos WHERE id = ?",
            (mov_id,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row["stock_general_anterior"] == 0
        assert row["stock_general_nuevo"] == 5

    async def test_stock_general_snapshot_reflects_existing_stock(
        self, db_session, producto_factory, ubicacion_factory, estante_factory
    ):
        """If the product already has 7 units at another ubicacion,
        ``stock_general_anterior=7`` (the bucket qty was NOT counted, so the
        lazy snapshot sees the existing ubicacion sum only). After rescuing
        4 units, ``stock_general_nuevo = 7 + 4 = 11``.

        Both ubicaciones share ONE explicitly-created estante — otherwise
        ``ubicacion_factory()``'s default would try to create a SECOND
        ``"UBFactory Shelf"`` and collide with migration 014's partial unique
        index on ``estantes.nombre``.
        """
        sku = await producto_factory(sku="PROD-R3")
        estante_id = await estante_factory(nombre="Test Shelf R3")
        ub_id_existing = await ubicacion_factory(
            estante_id=estante_id, producto_id=sku, stock_actual=7
        )
        ub_id_new = await ubicacion_factory(
            estante_id=estante_id, fila=2, columna=1
        )
        # Sanity check: the existing ubicacion's stock IS counted in
        # stock_general (this also verifies get_producto_stock_total behaves
        # as the helper expects).
        assert await repo.get_producto_stock_total(db_session, sku) == 7

        mov_id = await repo.create_movimiento_rescate_sin_ubicacion(
            db_session, sku, ub_id_new, qty=4
        )
        await db_session.commit()
        async with db_session.execute(
            "SELECT stock_general_anterior, stock_general_nuevo "
            "FROM movimientos WHERE id = ?",
            (mov_id,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row["stock_general_anterior"] == 7
        assert row["stock_general_nuevo"] == 11

    async def test_usuario_id_none_is_accepted(
        self, db_session, producto_factory, ubicacion_factory
    ):
        """``movimientos.usuario_id`` is nullable per migration 012; the
        helper accepts ``usuario_id=None`` so callers without a session
        (e.g. backfill-style batch scripts) can still record audit rows."""
        sku = await producto_factory(sku="PROD-R4")
        ub_id = await ubicacion_factory()
        mov_id = await repo.create_movimiento_rescate_sin_ubicacion(
            db_session, sku, ub_id, qty=2, usuario_id=None
        )
        await db_session.commit()
        async with db_session.execute(
            "SELECT usuario_id FROM movimientos WHERE id = ?",
            (mov_id,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row["usuario_id"] is None

    async def test_returns_movimiento_id(
        self, db_session, producto_factory, ubicacion_factory
    ):
        """The returned id matches the just-inserted row (contract: caller
        uses the id to follow up, e.g. set PRIMARY keys for routing)."""
        sku = await producto_factory(sku="PROD-R5")
        ub_id = await ubicacion_factory()
        mov_id = await repo.create_movimiento_rescate_sin_ubicacion(
            db_session, sku, ub_id, qty=3
        )
        await db_session.commit()
        assert mov_id is not None and mov_id > 0
        async with db_session.execute(
            "SELECT COUNT(*) FROM movimientos WHERE id = ?",
            (mov_id,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row[0] == 1


class TestMovimientoSalvageCleanup:
    """``create_movimiento_salvage_cleanup`` — Slice 2a additions."""

    async def test_inserts_row_with_new_tipo_literal_and_null_producto(
        self, db_session, ubicacion_factory
    ):
        """Migration 016 must accept ``'salvage_cleanup'`` AND the
        ``movimientos`` schema (migration 001:82 — ``producto_id TEXT`` with
        NO NOT NULL constraint) accepts ``producto_id = NULL``. Both proven
        by a single successful insert."""
        ub_id = await ubicacion_factory(producto_id=None, stock_actual=5)
        mov_id = await repo.create_movimiento_salvage_cleanup(
            db_session, ub_id, qty=5
        )
        await db_session.commit()
        async with db_session.execute(
            "SELECT tipo, producto_id, ubicacion_id, cantidad, "
            "stock_anterior, stock_nuevo "
            "FROM movimientos WHERE id = ?",
            (mov_id,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
        assert row["tipo"] == "salvage_cleanup"
        assert row["producto_id"] is None  # orphan by design — REQ-D-002
        assert row["ubicacion_id"] == ub_id
        assert row["cantidad"] == 5
        assert row["stock_anterior"] == 5  # ubicacion's prior stock_actual
        assert row["stock_nuevo"] == 0       # ubicacion will be zeroed

    async def test_stock_general_columns_are_zero_for_orphans(
        self, db_session, ubicacion_factory
    ):
        """Orphan has no product, so its salvage row records
        ``stock_general_anterior=0`` and ``stock_general_nuevo=0`` (the
        orphan contributes nothing to any product's stock_general)."""
        ub_id = await ubicacion_factory(producto_id=None, stock_actual=3)
        mov_id = await repo.create_movimiento_salvage_cleanup(
            db_session, ub_id, qty=3
        )
        await db_session.commit()
        async with db_session.execute(
            "SELECT stock_general_anterior, stock_general_nuevo "
            "FROM movimientos WHERE id = ?",
            (mov_id,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row["stock_general_anterior"] == 0
        assert row["stock_general_nuevo"] == 0

    async def test_usuario_id_none_is_accepted(self, db_session, ubicacion_factory):
        """Salvage is invoked by the one-shot backfill script which has no
        live user session — ``usuario_id=NULL`` for the audit row."""
        ub_id = await ubicacion_factory(producto_id=None, stock_actual=2)
        mov_id = await repo.create_movimiento_salvage_cleanup(
            db_session, ub_id, qty=2, usuario_id=None
        )
        await db_session.commit()
        async with db_session.execute(
            "SELECT usuario_id FROM movimientos WHERE id = ?",
            (mov_id,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row["usuario_id"] is None

    async def test_returns_movimiento_id(self, db_session, ubicacion_factory):
        """Returned id points at the inserted row."""
        ub_id = await ubicacion_factory(producto_id=None, stock_actual=1)
        mov_id = await repo.create_movimiento_salvage_cleanup(
            db_session, ub_id, qty=1
        )
        await db_session.commit()
        assert mov_id is not None and mov_id > 0
        async with db_session.execute(
            "SELECT COUNT(*) FROM movimientos WHERE id = ?",
            (mov_id,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row[0] == 1


class TestOriginalTiposStillAcceptedAfterMigration016:
    """Regression gate: migration 016's table-rebuild MUST preserve acceptance
    of the 4 original ``tipo`` literals. Direct SQL inserts (bypassing the
    helper functions) assert the CHECK constraint itself accepts each literal
    — proving the rebuild didn't drop any of them.
    """

    @pytest.mark.parametrize("tipo", ["alta", "ajuste", "asignacion", "desasignacion"])
    async def test_original_tipo_literal_still_accepted(
        self, db_session, producto_factory, ubicacion_factory, tipo
    ):
        sku = await producto_factory(sku="PROD-OLD")
        ub_id = await ubicacion_factory()
        # Direct SQL — bypass the helpers to assert the CHECK constraint
        # itself, not any helper-level validation.
        await db_session.execute(
            """
            INSERT INTO movimientos (
                usuario_id, producto_id, ubicacion_id, cantidad,
                stock_anterior, stock_nuevo, tipo,
                stock_general_anterior, stock_general_nuevo
            )
            VALUES (NULL, ?, ?, 1, 0, 1, ?, 0, 0)
            """,
            (sku, ub_id, tipo),
        )
        await db_session.commit()
        async with db_session.execute(
            "SELECT COUNT(*) FROM movimientos WHERE tipo = ?",
            (tipo,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row[0] >= 1