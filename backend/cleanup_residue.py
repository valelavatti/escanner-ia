"""One-time cleanup for residual soft-deleted / orphan estantes.

Run manually from the ``backend/`` directory::

    python cleanup_residue.py

This is NOT a migration — it is a one-time tool for cleaning up testing
residue. It does not change the schema and is not registered in
``app/core/migrations.py``.

What it does
------------
1. Finds all estantes that are either soft-deleted (``deleted_at IS NOT NULL``)
   or orphans (``deposito_id IS NULL``).
2. For each candidate, checks whether any of its ubicaciones has movimientos.
3. If NO movimientos anywhere: hard-deletes the ubicaciones, the estante, and
   the orphaned ``qr_cache`` PNG files.
4. If HAS movimientos AND is an orphan: reassigns it to Depósito Central
   (``deposito_id = 1``) so it is no longer an orphan and the audit trail
   stays reachable.
5. If HAS movimientos AND already belongs to a deposito: skips it (preserves
   the audit trail in its current home).

The script never touches estantes that have movimientos beyond the orphan
reassignment — ``movimientos.ubicacion_id`` is ``ON DELETE RESTRICT`` and the
audit trail is immutable.
"""

import asyncio
import sys
from pathlib import Path

import aiosqlite

# Allow ``from app.* import ...`` when run directly from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import get_settings  # noqa: E402
from app.core.database import configure_connection  # noqa: E402
from app.services.qr import delete_qr_cache_for  # noqa: E402


CENTRAL_DEPOSITO_ID = 1


async def _has_movimientos(db: aiosqlite.Connection, estante_id: int) -> bool:
    """Return True if any ubicacion of this estante has movimientos."""
    async with db.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM movimientos m
            JOIN ubicaciones u ON u.id = m.ubicacion_id
            WHERE u.estante_id = ?
        )
        """,
        (estante_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return bool(row[0])


async def _fetch_qr_valores(db: aiosqlite.Connection, estante_id: int) -> list[str]:
    async with db.execute(
        "SELECT qr_valor FROM ubicaciones WHERE estante_id = ?",
        (estante_id,),
    ) as cursor:
        return [r[0] for r in await cursor.fetchall()]


async def _hard_delete_estante(db: aiosqlite.Connection, estante_id: int) -> int:
    """Hard-delete an estante and its ubicaciones. Returns ubicaciones count.

    Caller MUST verify no movimientos reference these ubicaciones — the
    ``movimientos.ubicacion_id`` FK is ``ON DELETE RESTRICT``.
    """
    qr_valores = await _fetch_qr_valores(db, estante_id)

    await db.execute("BEGIN")
    try:
        # Order matters: ubicaciones first (FK ON DELETE RESTRICT from
        # estantes), then the estante itself.
        await db.execute(
            "DELETE FROM ubicaciones WHERE estante_id = ?",
            (estante_id,),
        )
        await db.execute("DELETE FROM estantes WHERE id = ?", (estante_id,))
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Best-effort qr_cache cleanup (outside the DB transaction).
    for qr_valor in qr_valores:
        delete_qr_cache_for(qr_valor)

    return len(qr_valores)


async def _reassign_to_central(db: aiosqlite.Connection, estante_id: int) -> None:
    """Attach an orphan estante to Depósito Central (id=1)."""
    await db.execute(
        "UPDATE estantes SET deposito_id = ? WHERE id = ?",
        (CENTRAL_DEPOSITO_ID, estante_id),
    )
    await db.commit()


async def _central_exists(db: aiosqlite.Connection) -> bool:
    async with db.execute(
        "SELECT 1 FROM depositos WHERE id = ?",
        (CENTRAL_DEPOSITO_ID,),
    ) as cursor:
        return await cursor.fetchone() is not None


async def main() -> None:
    settings = get_settings()
    print(f"DB path: {settings.db_path}")
    print("=" * 60)

    db = await aiosqlite.connect(settings.db_path, check_same_thread=False)
    db.row_factory = aiosqlite.Row
    await configure_connection(db)

    removed = 0
    kept = 0
    reassigned = 0
    skipped_no_central = 0

    try:
        central_ok = await _central_exists(db)
        if not central_ok:
            print(
                f"WARNING: Depósito Central (id={CENTRAL_DEPOSITO_ID}) not found. "
                "Orphans with movimientos cannot be reassigned and will be skipped."
            )

        async with db.execute(
            """
            SELECT id, nombre, deposito_id, deleted_at
            FROM estantes
            WHERE deleted_at IS NOT NULL OR deposito_id IS NULL
            ORDER BY id
            """
        ) as cursor:
            rows = await cursor.fetchall()
        candidates = [dict(r) for r in rows]

        print(f"Candidate estantes (soft-deleted or orphans): {len(candidates)}")
        print()

        for estante in candidates:
            eid = estante["id"]
            label = (
                f"#{eid} '{estante['nombre']}' "
                f"(deposito_id={estante['deposito_id']}, "
                f"deleted_at={estante['deleted_at']})"
            )
            has_movs = await _has_movimientos(db, eid)
            is_orphan = estante["deposito_id"] is None

            if has_movs and is_orphan:
                if not central_ok:
                    skipped_no_central += 1
                    print(
                        f"  [SKIP]       {label} — orphan with movimientos, "
                        "but Depósito Central is missing"
                    )
                    continue
                await _reassign_to_central(db, eid)
                reassigned += 1
                print(
                    f"  [REASSIGNED] {label} — orphan with movimientos, "
                    f"attached to Depósito Central (id={CENTRAL_DEPOSITO_ID})"
                )
                continue

            if has_movs:
                kept += 1
                print(
                    f"  [KEPT]       {label} — has movimientos (audit trail preserved)"
                )
                continue

            ubi_count = await _hard_delete_estante(db, eid)
            removed += 1
            print(
                f"  [REMOVED]    {label} — {ubi_count} ubicaciones + qr_cache cleaned"
            )

        print()
        print("=" * 60)
        print(
            f"Removed {removed} estantes, kept {kept} with movements, "
            f"reassigned {reassigned} orphans"
            + (f", skipped {skipped_no_central} (no Central)" if skipped_no_central else "")
            + "."
        )
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
