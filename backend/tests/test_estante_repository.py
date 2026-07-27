"""Part A - Estante fantasma (ghost shelf) regression tests.

Scenarios A1-A4 from spec #295 (sdd/estante-stock-sin-ubicacion/spec):
- A1: recreate a soft-deleted shelf name succeeds, returns a NEW id.
- A2: two active shelves cannot share a name even with a ghost present.
- A3: a soft-deleted shelf is hidden from the active list.
- A4: a DB carrying multiple soft-deleted ghost rows still allows recreating
  each name (simulating the 3 production ghost rows: id=2 'A', id=5 'Pasillo
  1', id=9 'Estante 1').

These tests REQUIRE migration 014 (`014_estante_nombre_partial_unique.sql`)
to have replaced the legacy `estantes.nombre UNIQUE` column constraint with
the partial unique index `estantes_nombre_active_idx ON estantes(nombre)
WHERE deleted_at IS NULL`. Without migration 014, A1 and A4 would raise
`aiosqlite.IntegrityError` on the legacy UNIQUE constraint (the bug) when
recreating the ghost name; A2 would fail the same way on the second active
insert. With 014 applied, A1/A4 recursive-recreates all succeed, and A2
fails cleanly when there's already an ACTIVE shelf with the same name.

The harness `db_session` fixture (conftest.py) opens a fresh per-test
`:memory:` SQLite connection with ALL migrations applied (001..014) and
PRAGMA `foreign_keys = ON`. Each test is hermetic - no shared state.

Naming/dimensions convention (avoids the unrelated `ubicaciones.qr_valor`
UNIQUE constraint):
- The GHOST (about to be soft-deleted) shelf is created with a 4x3 grid, so
  its ubicaciones get QR values like `"<name>-F1-C1"` ... `"<name>-F4-C3"`.
- The RECREATE uses 1x1, so its single ubicacion gets QR value `"<name>"`
  (the bare name per the adaptive QR format from `generate_qr_valor`).
- The two QR value sets never collide on `ubicaciones.qr_valor UNIQUE`, so
  the only uniqueness being exercised is `estantes_nombre_active_idx`.
"""

from __future__ import annotations

import aiosqlite
import pytest

from app.repositories.estante_repository import (
    create_estante,
    get_estante_by_name,
    list_estantes,
    soft_delete_estante,
)


# ---------------------------------------------------------------------------
# Helper: fetch ANY estante row by id (including soft-deleted ones).
# The repository's `get_estante_by_id` filters `deleted_at IS NULL` (correct
# app-layer behavior), but tests need to inspect ghost rows directly to
# assert they are preserved with their data intact (REQ-A-005).
# ---------------------------------------------------------------------------

async def _fetch_estante_raw(db: aiosqlite.Connection, estante_id: int) -> dict | None:
    async with db.execute(
        "SELECT * FROM estantes WHERE id = ?", (estante_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row is not None else None


async def _index_names(db: aiosqlite.Connection, table: str) -> list[str]:
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ? ORDER BY name",
        (table,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


class TestGhostShelfScenarios:
    """Regression tests for the ghost-shelf bug (Part A, A0-A4)."""

    GHOST_FILAS = 4
    GHOST_COLUMNAS = 3
    RECREATE_FILAS = 1
    RECREATE_COLUMNAS = 1

    async def test_a0_partial_unique_index_in_place(self, db_session):
        """Verify migration 014 created the partial index and dropped the
        legacy unconditional UNIQUE auto-index on `estantes.nombre`.

        Anchors REQ-A-003 (partial unique index `estantes_nombre_active_idx`
        exists) and REQ-A-004 (legacy `UNIQUE` column constraint is gone -
        detected by the absence of its backing auto-index
        `sqlite_autoindex_estantes_1`).
        """
        names = await _index_names(db_session, "estantes")

        # REQ-A-003: new partial unique index exists.
        assert "estantes_nombre_active_idx" in names, (
            "Partial unique index 'estantes_nombre_active_idx' MUST exist on "
            "estantes(nombre) WHERE deleted_at IS NULL after migration 014."
        )
        # Index from migration 002 recreated by the rebuild.
        assert "idx_estantes_deleted_at" in names, (
            "Software filter index 'idx_estantes_deleted_at' MUST be recreated "
            "by migration 014 (it gets dropped with the old table)."
        )
        # REQ-A-004: legacy UNIQUE auto-index on `nombre` is GONE.
        assert "sqlite_autoindex_estantes_1" not in names, (
            "Legacy unconditional UNIQUE auto-index on estantes.nombre MUST be "
            "dropped by migration 014 (otherwise soft-deleted rows keep blocking "
            "recreation of the same name)."
        )

    async def test_a1_recreate_soft_deleted_name_succeeds_with_new_id(self, db_session):
        # GIVEN an active 4x3 shelf named "A" exists.
        original_id = await create_estante(
            db_session, nombre="A", orden_visual=0,
            filas=self.GHOST_FILAS, columnas=self.GHOST_COLUMNAS,
        )
        assert original_id > 0

        # WHEN the user soft-deletes it.
        assert await soft_delete_estante(db_session, original_id) is True

        # AND recreates a 1x1 shelf with the same name.
        recreated_id = await create_estante(
            db_session, nombre="A", orden_visual=0,
            filas=self.RECREATE_FILAS, columnas=self.RECREATE_COLUMNAS,
        )

        # THEN the recreation succeeds with a NEW id distinct from the deleted one.
        assert recreated_id != original_id

        # AND the original (ghost) row is preserved with `deleted_at` set
        # (REQ-A-005: migration does NOT touch ghost rows).
        ghost_row = await _fetch_estante_raw(db_session, original_id)
        assert ghost_row is not None
        assert ghost_row["deleted_at"] is not None
        assert ghost_row["nombre"] == "A"

        # AND the new row is active.
        active_row = await _fetch_estante_raw(db_session, recreated_id)
        assert active_row is not None
        assert active_row["deleted_at"] is None
        assert active_row["nombre"] == "A"

        # AND the active list contains the recreated shelf (by id), not the ghost.
        active = await list_estantes(db_session, include_deleted=False)
        active_ids = [r["id"] for r in active]
        assert recreated_id in active_ids
        assert original_id not in active_ids
        assert "A" in [r["nombre"] for r in active]

    async def test_a2_duplicate_active_name_blocked_then_ok_after_delete(
        self, db_session
    ):
        # GIVEN an active shelf "B" exists.
        first_id = await create_estante(
            db_session, nombre="B", orden_visual=0,
            filas=self.GHOST_FILAS, columnas=self.GHOST_COLUMNAS,
        )

        # WHEN the user tries to create another active "B" while the first is
        # still active, the partial unique index `estantes_nombre_active_idx`
        # fires (both rows would have deleted_at IS NULL).
        with pytest.raises(aiosqlite.IntegrityError) as exc_info:
            await create_estante(
                db_session, nombre="B", orden_visual=0,
                filas=self.RECREATE_FILAS, columnas=self.RECREATE_COLUMNAS,
            )
        # The integrity error MUST come from the `estantes.nombre` unique
        # constraint (the partial unique index), not from any nearby CHECK or
        # the unrelated `ubicaciones.qr_valor` constraint.
        assert "estantes" in str(exc_info.value)
        assert "nombre" in str(exc_info.value)

        # AND the first row is still active and findable by name.
        still_active = await get_estante_by_name(db_session, "B")
        assert still_active is not None
        assert still_active["id"] == first_id

        # WHEN the user soft-deletes the active "B".
        assert await soft_delete_estante(db_session, first_id) is True

        # AND recreates "B".
        new_id = await create_estante(
            db_session, nombre="B", orden_visual=0,
            filas=self.RECREATE_FILAS, columnas=self.RECREATE_COLUMNAS,
        )

        # THEN the recreation succeeds with a NEW id (partial index sees only
        # active rows; the soft-deleted "B" is excluded from it).
        assert new_id != first_id
        active_after = await get_estante_by_name(db_session, "B")
        assert active_after is not None
        assert active_after["id"] == new_id

    async def test_a3_soft_deleted_estante_hidden_from_active_list(self, db_session):
        # GIVEN an active 4x3 shelf "Estante 1".
        shelf_id = await create_estante(
            db_session, nombre="Estante 1", orden_visual=0,
            filas=self.GHOST_FILAS, columnas=self.GHOST_COLUMNAS,
        )

        # Sanity: appears in active list before deletion.
        before = await list_estantes(db_session, include_deleted=False)
        assert "Estante 1" in [r["nombre"] for r in before]

        # WHEN the user soft-deletes it.
        assert await soft_delete_estante(db_session, shelf_id) is True

        # THEN the deleted shelf does NOT appear in the active list
        # (REQ-A-008: GET /estantes excludes soft-deleted rows).
        after = await list_estantes(db_session, include_deleted=False)
        assert "Estante 1" not in [r["nombre"] for r in after]

        # AND get_estante_by_name returns None (filters deleted_at IS NULL).
        assert await get_estante_by_name(db_session, "Estante 1") is None

        # AND include_deleted=True surfaces the ghost row.
        with_ghosts = await list_estantes(db_session, include_deleted=True)
        assert "Estante 1" in [r["nombre"] for r in with_ghosts]

    async def test_a4_three_ghost_rows_then_recreate_each(self, db_session):
        # GIVEN the 3 production ghost names - simulated by creating + soft
        # deleting each in a fresh migrations-014-applied DB (mirrors the
        # prod state: rows with deleted_at IS NOT NULL whose names would
        # block recreation under the legacy UNIQUE constraint).
        ghost_names = ["A", "Pasillo 1", "Estante 1"]
        ghost_ids: list[int] = []
        for name in ghost_names:
            shelf_id = await create_estante(
                db_session, nombre=name, orden_visual=0,
                filas=self.GHOST_FILAS, columnas=self.GHOST_COLUMNAS,
            )
            assert await soft_delete_estante(db_session, shelf_id) is True
            ghost_ids.append(shelf_id)

        # WHEN the user recreates each name (1x1 - different qr_valor
        # namespace from the 4x3 ghost's ubicaciones).
        # THEN every recreate succeeds and returns a NEW id for an ACTIVE row.
        for original_id, name in zip(ghost_ids, ghost_names):
            recreated_id = await create_estante(
                db_session, nombre=name, orden_visual=0,
                filas=self.RECREATE_FILAS, columnas=self.RECREATE_COLUMNAS,
            )
            assert recreated_id != original_id

            # Ghost row preserved soft-deleted with its name intact.
            ghost_row = await _fetch_estante_raw(db_session, original_id)
            assert ghost_row is not None
            assert ghost_row["deleted_at"] is not None
            assert ghost_row["nombre"] == name

            # New row is active with the same name.
            active_row = await _fetch_estante_raw(db_session, recreated_id)
            assert active_row is not None
            assert active_row["deleted_at"] is None
            assert active_row["nombre"] == name

            # Active list contains the recreated row, not the ghost.
            active_list = await list_estantes(db_session, include_deleted=False)
            active_ids = [r["id"] for r in active_list]
            assert recreated_id in active_ids
            assert original_id not in active_ids

        # AND the final active list contains the 3 new active rows (plus the
        # seed "Suelto" shelf from migration 004 - confirms the rebuild did
        # NOT touch the seed row).
        final_active = await list_estantes(db_session, include_deleted=False)
        final_names = sorted(r["nombre"] for r in final_active)
        assert "A" in final_names
        assert "Pasillo 1" in final_names
        assert "Estante 1" in final_names
        assert "Suelto" in final_names