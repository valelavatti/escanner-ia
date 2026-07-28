"""One-shot, idempotent backfill: zero orphan ``ubicaciones`` with salvage audit.

What this script does
---------------------
Iterates the orphan query

    SELECT id, stock_actual FROM ubicaciones
    WHERE producto_id IS NULL AND stock_actual > 0
    ORDER BY id

("orphan" = a physical ubicacion holding ``stock_actual > 0`` but not
attributable to any product — legacy rows collected before the
unassign-cleanup audit fix landed). For each orphan, in ONE
``BEGIN IMMEDIATE`` / ``commit`` transaction:

1. Write a ``movimientos`` row of ``tipo='salvage_cleanup'`` with
   - ``cantidad`` = the orphan's ``stock_actual`` (units being cleaned up)
   - ``ubicacion_id`` = the orphan's ``id`` (the real freed cell, NOT NULL —
     matches the post-unassign-audit-fix invariant)
   - ``producto_id = NULL`` (the orphan has no product BY DEFINITION; see
     REQ-D-002 / REQ-D-003)

   The audit row is written via the shared repository helper
   :func:`movimiento_repository.create_movimiento_salvage_cleanup` (added in
   Slice 2a). The helper hard-codes ``producto_id = NULL`` and records
   ``stock_anterior = qty``, ``stock_nuevo = 0`` (the cell is being zeroed in
   the same transaction), ``stock_general_anterior = stock_general_nuevo = 0``
   (an orphan contributes nothing to any product's ``stock_general``).

2. ``UPDATE ubicaciones SET stock_actual = 0 WHERE id = ?`` for that orphan.

The script NEVER routes orphan qty into the ``stock_sin_ubicacion`` bucket
(REQ-D-007 / user decision D1: orphans are test data — ≈56 units — and the
team decided to drop them rather than credit a product). Only the audit trail
(the ``salvage_cleanup`` movimiento) is preserved.

Idempotency (REQ-D-001, REQ-D-002)
---------------------------------
The orphan query filters by ``stock_actual > 0``. The first run zeroes every
matching orphan; therefore the SECOND run finds 0 rows, writes 0 movimientos,
and modifies 0 ubicaciones. Re-running the script is safe and can be wired
through a startup gate or cron trigger. The script reports backfilled count
which is 0 on any re-run after a successful first run.

Per-orphan transaction & failure isolation (REQ-D-005, REQ-D-006)
-----------------------------------------------------------------
Each orphan is processed inside its own ``BEGIN IMMEDIATE`` / ``commit``
envelope (design R3 — single-writer lock acquired up front, atomic, no read-
modify-write race). If one orphan throws (FK violation, disk full, etc.),
the script ``rollback()``s ONLY that orphan's transaction, logs the error,
and continues with the next. One orphan failing does NOT break the rest.

Callable both as a module and as a standalone script (orchestrator's
delivery-of-record for Slice 4 of change ``estante-stock-sin-ubicacion``)::

    python -m backend.app.services.backfill_orphans
    python backend/app/services/backfill_orphans.py

Tests invoke ``await backfill_orphans.main(db_session)`` with their own
in-memory aiosqlite connection (conftest ``db_session`` fixture). When called
WITHOUT a connection, ``main()`` opens the production DB (settings.db_path),
configures it via :func:`app.core.database.configure_connection`, runs the
iteration, and closes the connection before returning.

Spec anchors: REQ-D-001..007.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import aiosqlite

# Standalone-execution path insertion: ensure ``backend/`` (this file's
# parents[2]) is on sys.path so ``from app.*`` imports resolve when this
# script is run directly via ``python backend/app/services/backfill_orphans.py``
# (mirrors the pattern in ``backend/cleanup_residue.py``). When invoked via
# ``python -m backend.app.services.backfill_orphans`` the cwd (repo root) is
# already on sys.path and this insert is redundant but harmless.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_db_connection  # noqa: E402
from app.repositories import movimiento_repository  # noqa: E402


# Orphan query: pre-existing ubicaciones holding stock but no product.
# The ``stock_actual > 0`` filter is what makes this script idempotent
# (REQ-D-001 / REQ-D-002 — re-runs find 0 rows after a successful first run).
_ORPHAN_QUERY = """
    SELECT id, stock_actual
      FROM ubicaciones
     WHERE producto_id IS NULL
       AND stock_actual > 0
     ORDER BY id
"""


async def main(conn: Optional[aiosqlite.Connection] = None) -> int:
    """Backfill orphan ``ubicaciones``: write a ``salvage_cleanup`` movimiento
    per orphan and zero its ``stock_actual``.

    Args:
        conn: An already-open, configured aiosqlite connection. If ``None`` the
            function opens the production connection via
            :func:`app.core.database.get_db_connection` (which sets
            ``row_factory = aiosqlite.Row`` and applies the project PRAGMAs),
            owns its lifecycle, and ``close()``s it before returning. Tests
            pass in their own ``:memory:`` connection (conftest ``db_session``
            fixture) for clean-room isolation.

    Returns:
        The number of orphans actually backfilled (i.e., ``salvage_cleanup``
        rows written and ubicaciones zeroed by this invocation). A second run
        after a successful first run returns ``0`` — that's the idempotency
        guarantee (REQ-D-001, REQ-D-002).
    """
    owns_connection = conn is None
    if owns_connection:
        settings = get_settings()
        print(f"backfill_orphans: opening DB at {settings.db_path}")
        conn = await get_db_connection(settings.db_path)

    try:
        async with conn.execute(_ORPHAN_QUERY) as cursor:
            rows = await cursor.fetchall()
        candidates = [dict(r) for r in rows]

        if not candidates:
            print(
                "backfill_orphans: no orphans found, nothing to do "
                "(idempotent no-op)"
            )
            return 0

        print(
            f"backfill_orphans: found {len(candidates)} orphan ubicacion(s) "
            f"to backfill"
        )

        n_backfilled = 0
        for orphan in candidates:
            ub_id = orphan["id"]
            qty = orphan["stock_actual"]
            print(
                f"backfill_orphans: orphan ubicacion id={ub_id} qty={qty} → "
                f"salvage_cleanup movimiento + zero stock_actual"
            )
            try:
                # One ``BEGIN IMMEDIATE`` / ``commit`` per orphan (design R3):
                # the movimiento INSERT and the ubicacion UPDATE are atomic.
                await conn.execute("BEGIN IMMEDIATE")
                await movimiento_repository.create_movimiento_salvage_cleanup(
                    conn,
                    ubicacion_id=ub_id,
                    qty=qty,
                    usuario_id=None,
                )
                await conn.execute(
                    "UPDATE ubicaciones SET stock_actual = 0 WHERE id = ?",
                    (ub_id,),
                )
                await conn.commit()
                n_backfilled += 1
            except Exception as exc:
                # Failure isolation (REQ-D-005, REQ-D-006): one orphan failing
                # MUST NOT break the rest. Rollback THIS orphan's tx, log, and
                # continue with the next.
                try:
                    await conn.rollback()
                except Exception:
                    # No active transaction to rollback — silently swallow.
                    pass
                print(
                    f"backfill_orphans: ERROR orphan ubicacion id={ub_id} "
                    f"failed: {exc!r} (continuing with remaining orphans)"
                )
                continue

        print(
            f"backfill_orphans: backfilled {n_backfilled}/{len(candidates)} "
            f"orphan(s)"
        )
        return n_backfilled
    finally:
        if owns_connection:
            await conn.close()


if __name__ == "__main__":
    asyncio.run(main())