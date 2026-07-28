"""Tests for Slice 3 — Part C: sin-ubicacion view exposure.

Repo-level coverage of:

- ``movimiento_repository.get_producto_ubicaciones`` — the new 3rd "bucket"
  branch (REQ-C-001, REQ-C-002) that surfaces one synthetic row per
  ``stock_sin_ubicacion`` row for the product, alongside the physical
  ubicaciones.
- ``ProductoUbicacionItem`` Pydantic schema accepting null ``ubicacion_id``
  and ``qr_valor`` (REQ-C-003) — verified by constructing the schema from
  the bucket row's raw dict through the same path the endpoint uses.

Scenarios
---------

- **C1** — product has 2 physical ubicaciones + 10 units in the bucket:
  ``get_producto_ubicaciones`` returns 3 items; 2 with non-null
  ``ubicacion_id``/``qr_valor``, 1 with ``ubicacion_id=None``,
  ``qr_valor=None``, ``estante_nombre='SIN UBICACION'``, ``stock=10``.
- **C2** — FE-shape coverage (no frontend harness exists per init #289, so
  cover at the schema/return-shape layer): the bucket row from C1's repo
  output, transformed via the same path the endpoint uses
  (``productos.py:101-115``: ``ubicacion_repository.compute_labels`` then
  ``ProductoUbicacionItem(**fields)``), produces a valid Pydantic instance
  with ``ubicacion_id=None``, ``qr_valor=None`` — so the FE will receive a
  properly-shaped object.
- **C3** — product has 0 physical ubicaciones but a bucket row with qty=4:
  endpoint returns exactly 1 item with ``ubicacion_id=None``,
  ``qr_valor=None``, ``stock=4``.
- **C4** — product has 0 physical ubicaciones AND no bucket row:
  endpoint returns an EMPTY list (NOT a synthetic empty bucket). R1
  invariant: absence of a bucket row == 0 units — the 3rd branch only
  fires when ``stock_sin_ubicacion`` has a row for this product.
- **R5** — Suelto regression: a Suelto-only product (no bucket row, only a
  Suelto movimiento) returns exactly 1 item with the REAL Suelto
  ``ubicacion_id`` (id=1, qr_valor='Suelto') — NOT null. Suelto is a
  PHYSICAL storage modality (real ``ubicaciones`` row); the bucket is a
  TRANSIT state. They never contaminate each other (design §1 R5:
  discrimination is at the QUERY layer, not the data layer).

Carry-forward risk #3 (from Slice 2a): each test creates ONE shared
``estante_id`` via :func:`estante_factory` and uses distinct
``(fila, columna)`` per :func:`ubicacion_factory` call. The conftest's
default ``"UBFactory Shelf"`` estante name would collide with migration
014's partial unique index if two ubicacion_factory calls each silently
created a new estante — so the tests pass an explicit ``estante_id`` and
distinct ``(fila, columna)``.

``estante_factory`` does NOT expose ``deposito_id``, but the regular and
Suelto branches in ``get_producto_ubicaciones`` INNER JOIN ``depositos`` —
so test-created estantes are attached to the Central deposito (id=1, seeded
by migration 006) via a small inline UPDATE in a helper below. The R5
Suelto shelf doesn't need that — migration 006 already attaches it.

Bucket rows are populated via ``stock_sin_ubicacion_repository.upsert_add``
(the same path used by Slice 2b's surgery).

Spec anchors: REQ-C-001_007, REQ-X-006, R1, R5.
"""

from __future__ import annotations

import pytest

from app.repositories import movimiento_repository as _mov_repo
from app.repositories import stock_sin_ubicacion_repository as _bucket_repo
from app.repositories import ubicacion_repository as _ub_repo
from app.schemas.productos import ProductoUbicacionItem


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test-scoped async helpers (NOT fixtures: small inline boilerplate to keep
# the scenario bodies focused on assertions).
# ---------------------------------------------------------------------------


async def _attach_to_central_deposito(db, estante_id: int) -> None:
    """Attach ``estante_id`` to the Central deposito (id=1, seeded by
    migration 006).

    The conftest's ``estante_factory`` doesn't expose ``deposito_id``, but
    the regular and Suelto branches of ``get_producto_ubicaciones`` INNER
    JOIN ``depositos`` — without this, the regular branch's JOIN drops the
    test-created ubicacion and C1 would silently return 2 items instead of 3.
    """
    await db.execute(
        "UPDATE estantes SET deposito_id = 1 WHERE id = ?",
        (estante_id,),
    )
    await db.commit()


def _find_bucket_row(rows: list[dict]) -> dict | None:
    """Return the first row with ``ubicacion_id is None`` (the synthetic
    sin-ubicacion item), or ``None`` if there isn't one."""
    for r in rows:
        if r["ubicacion_id"] is None:
            return r
    return None


def _count_by_ubicacion_id_null(rows: list[dict]) -> tuple[int, int]:
    """Return ``(n_null, n_set)`` for ``ubicacion_id`` in ``rows``."""
    n_null = sum(1 for r in rows if r["ubicacion_id"] is None)
    n_set = sum(1 for r in rows if r["ubicacion_id"] is not None)
    return n_null, n_set


# ---------------------------------------------------------------------------
# C1 — 2 physical ubicaciones + 10 in bucket → 3 items
# ---------------------------------------------------------------------------

async def test_c1_two_physical_plus_bucket(
    db_session, estante_factory, producto_factory, ubicacion_factory
):
    # GIVEN: Central deposito auto-seeded (migration 006), a 2x2 estante
    # attached to it, a product P with 2 ubicaciones on that estante
    # (each stock_actual=3, distinct (fila, columna) so qr_valor stays
    # unique), and 10 units in P's bucket.
    estante_id = await estante_factory(nombre="C1 Shelf", filas=2, columnas=2)
    await _attach_to_central_deposito(db_session, estante_id)
    sku_p = await producto_factory(sku="C1-P", codigo_de_barra="BAR-C1")
    ub1 = await ubicacion_factory(
        estante_id=estante_id, fila=1, columna=1, producto_id=sku_p, stock_actual=3
    )
    ub2 = await ubicacion_factory(
        estante_id=estante_id, fila=1, columna=2, producto_id=sku_p, stock_actual=3
    )
    await _bucket_repo.upsert_add(db_session, sku_p, 10)

    # WHEN: the user queries ubicaciones for P (admin mode: deposito_ids=None).
    rows = await _mov_repo.get_producto_ubicaciones(db_session, sku_p)

    # THEN: 3 items — 2 physical (ubicacion_id set, qr_valor set), 1 bucket.
    assert len(rows) == 3
    n_null, n_set = _count_by_ubicacion_id_null(rows)
    assert n_null == 1
    assert n_set == 2

    physical_rows = [r for r in rows if r["ubicacion_id"] is not None]
    for r in physical_rows:
        assert r["ubicacion_id"] in (ub1, ub2)
        assert r["qr_valor"] is not None
        assert r["qr_valor"] != ""
        assert r["estante_nombre"] == "C1 Shelf"
        assert r["stock"] == 3

    bucket_row = _find_bucket_row(rows)
    assert bucket_row is not None
    assert bucket_row["ubicacion_id"] is None
    assert bucket_row["qr_valor"] is None
    assert bucket_row["estante_nombre"] == "SIN UBICACION"
    assert bucket_row["stock"] == 10
    assert bucket_row["deposito_nombre"] == ""


# ---------------------------------------------------------------------------
# C2 — FE-shape: bucket row → ProductoUbicacionItem (Pydantic Optional)
# ---------------------------------------------------------------------------

async def test_c2_pydantic_shape_of_bucket_row(
    db_session, estante_factory, producto_factory, ubicacion_factory
):
    """Cover C2 (frontend rendering) at the schema layer.

    The bucket row from C1's repo output, transformed via the same path
    used by the endpoint (``productos.py:101-115``: ``compute_labels`` then
    ``ProductoUbicacionItem(**fields)``), produces a valid Pydantic instance
    with the expected null fields — proving the FE will receive a
    properly-shaped object. No frontend harness exists (init #289); this
    is the closest type-level guarantee compensating for the absence.
    """
    estante_id = await estante_factory(nombre="C2 Shelf", filas=2, columnas=2)
    await _attach_to_central_deposito(db_session, estante_id)
    sku_p = await producto_factory(sku="C2-P", codigo_de_barra="BAR-C2")
    await ubicacion_factory(
        estante_id=estante_id, fila=1, columna=1, producto_id=sku_p, stock_actual=2
    )
    await _bucket_repo.upsert_add(db_session, sku_p, 7)

    rows = await _mov_repo.get_producto_ubicaciones(db_session, sku_p)
    assert len(rows) == 2

    # Mirror the endpoint loop (productos.py:101-115) for every row.
    items = []
    for u in rows:
        fila_label, columna_label = _ub_repo.compute_labels(u)
        items.append(
           ProductoUbicacionItem(
                ubicacion_id=u["ubicacion_id"],
                estante_nombre=u["estante_nombre"],
                qr_valor=u["qr_valor"],
                fila=u["fila"],
                columna=u["columna"],
                fila_label=fila_label,
                columna_label=columna_label,
                stock=int(u["stock"]),
                deposito_nombre=u["deposito_nombre"],
            )
        )

    # 1 physical + 1 bucket — both Pydantic-validated without raising.
    bucket_items = [i for i in items if i.ubicacion_id is None]
    physical_items = [i for i in items if i.ubicacion_id is not None]
    assert len(bucket_items) == 1
    assert len(physical_items) == 1

    bi = bucket_items[0]
    assert bi.ubicacion_id is None
    assert bi.qr_valor is None
    assert bi.estante_nombre == "SIN UBICACION"
    assert bi.stock == 7
    assert bi.deposito_nombre == ""


# ---------------------------------------------------------------------------
# C3 — only bucket stock, no physical ubicaciones
# ---------------------------------------------------------------------------

async def test_c3_only_bucket_stock(db_session, producto_factory):
    sku_p = await producto_factory(sku="C3-P", codigo_de_barra="BAR-C3")
    await _bucket_repo.upsert_add(db_session, sku_p, 4)

    rows = await _mov_repo.get_producto_ubicaciones(db_session, sku_p)

    assert len(rows) == 1
    assert rows[0]["ubicacion_id"] is None
    assert rows[0]["qr_valor"] is None
    assert rows[0]["estante_nombre"] == "SIN UBICACION"
    assert rows[0]["stock"] == 4
    assert rows[0]["deposito_nombre"] == ""


# ---------------------------------------------------------------------------
# C4 — 0 stock and 0 bucket → 0 items (NOT a synthetic empty bucket)
# ---------------------------------------------------------------------------

async def test_c4_zero_stock_zero_bucket(db_session, producto_factory):
    sku_p = await producto_factory(sku="C4-P", codigo_de_barra="BAR-C4")

    rows = await _mov_repo.get_producto_ubicaciones(db_session, sku_p)

    # R1 invariant: absence of a bucket row == 0 units; the 3rd branch only
    # fires when ``stock_sin_ubicacion`` has a row for this product. No
    # synthetic empty bucket is emitted.
    assert len(rows) == 0


# ---------------------------------------------------------------------------
# R5 — Suelto regression: Suelto-only product NEVER appears as sin-ubicacion
# ---------------------------------------------------------------------------

async def test_r5_suelto_only_never_synthetic(db_session, producto_factory):
    # GIVEN: migration 004 seeds the Suelto shelf (id=1 typically, qr_valor='Suelto')
    # with a single 1x1 ubicacion. Migration 006 attaches the Suelto estante
    # to the Central deposito (id=1). Create product P and insert ONE alta
    # movimiento at the Suelto ubicacion with cantidad=7 for P. Do NOT create
    # a bucket row for P.
    sku_p = await producto_factory(sku="R5-P", codigo_de_barra="BAR-R5")

    # Locate the Suelto ubicacion's id (assert rather than hardcode, in case
    # the migration order ever shifts).
    async with db_session.execute(
        "SELECT u.id AS ubicacion_id, u.qr_valor AS qr_valor "
        "FROM ubicaciones u "
        "JOIN estantes e ON e.id = u.estante_id "
        "WHERE e.nombre = 'Suelto' AND e.deleted_at IS NULL"
    ) as cursor:
        suelto_row = await cursor.fetchone()
    assert suelto_row is not None, (
        "Migration 004 must seed the Suelto shelf + ubicacion"
    )
    suelto_ubicacion_id = int(suelto_row["ubicacion_id"])
    assert suelto_row["qr_valor"] == "Suelto"

    # 5 placeholders: producto_id, ubicacion_id, cantidad, stock_nuevo,
    # stock_general_nuevo (the rest are literal 0 / 'alta').
    await db_session.execute(
        """
        INSERT INTO movimientos
            (producto_id, ubicacion_id, cantidad, stock_anterior, stock_nuevo,
             tipo, stock_general_anterior, stock_general_nuevo)
        VALUES (?, ?, ?, 0, ?, 'alta', 0, ?)
        """,
        (sku_p, suelto_ubicacion_id, 7, 7, 7),
    )
    await db_session.commit()

    # WHEN: the user queries ubicaciones for P.
    rows = await _mov_repo.get_producto_ubicaciones(db_session, sku_p)

    # THEN: exactly 1 item — the Suelto row (real ubicacion_id), NOT a
    # synthetic sin-ubicacion row. Suelto is a PHYSICAL storage modality
    # (loose units in a bin); the bucket is a TRANSIT state (units with no
    # physical cell yet). The two never confuse each other (design §1 R5:
    # discrimination is at the QUERY layer, not the data layer).
    assert len(rows) == 1
    assert rows[0]["ubicacion_id"] == suelto_ubicacion_id
    assert rows[0]["ubicacion_id"] is not None  # explicit: NOT null
    assert rows[0]["qr_valor"] == "Suelto"
    assert rows[0]["estante_nombre"] == "Suelto"
    assert rows[0]["stock"] == 7

    # R5 regression core: NO synthetic bucket row was emitted. The 3rd
    # branch only fires for products WITH a ``stock_sin_ubicacion`` row.
    bucket_rows = [r for r in rows if r["ubicacion_id"] is None]
    assert len(bucket_rows) == 0