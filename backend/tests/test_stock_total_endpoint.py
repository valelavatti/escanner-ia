"""Tests for Slice 6 Phase C — stock-total endpoint + admin sin-ubicacion listing.

Covers the two endpoint additions to ``backend/app/api/v1/endpoints/productos.py``:

- ``GET /{codigo_de_barra}/stock-total`` — now returns the new
  :class:`ProductoStockTotal` schema INCLUDING the ``stock_sin_ubicacion``
  field (the bucket qty surfaced separately from ``stock_total`` per
  REQ-X-002 + REQ-B-009). The endpoint ADDS the bucket qty to the
  ``movimiento_repository.get_producto_stock_total`` physical+Suelto sum
  so the displayed ``stock_total`` invariant finally holds at the API
  boundary (REQ-B-009 recovery — the repo function covers physical +
  Suelto ONLY, the bucket is a separate flow).
- ``GET /sin-ubicacion`` — admin-guarded listing (:func:`require_admin`)
  of every product whose ``stock_sin_ubicacion`` row holds units (Slice 6 /
  Frontend Point 5). Read-only — no admin actions on the bucket.

Test approach
-------------
Mirrors the established codebase pattern (see
``test_sin_ubicacion_view.py`` + ``test_assign_overwrite_edge_case.py`):
there is no FastAPI ``TestClient`` HTTP-layer harness in this project
(init #289), so we invoke the route handler functions DIRECTLY in-process.
FastAPI's ``Depends(...))`` defaults are inert markers when the function
is called outside the DI container — we pass ``db`` and ``user``
explicitly. The ``sku`` query param default is a FastAPI ``Query`` FieldInfo
object (NOT ``None``), so tests pass ``sku=None`` explicitly to exercise
the barcode-lookup branch. Route-registration order (``/sin-ubicacion``
declared BEFORE ``/{codigo_de_barra}`` to prevent FastAPI from binding
``"sin-ubicacion"`` as a ``codigo_de_barra`` value) is verified separately
by inspecting ``productos.py``.

Spec anchors: REQ-X-002, REQ-B-009, Slice 6 / Frontend Points 4 & 5.
"""

from __future__ import annotations

import pytest

from app.api.v1.endpoints.productos import (
    get_producto_stock_total,
    list_stock_sin_ubicacion,
)
from app.repositories import stock_sin_ubicacion_repository as _bucket_repo
from app.schemas.auth import UsuarioResponse


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test-scoped helpers
# ---------------------------------------------------------------------------


def _admin_user() -> UsuarioResponse:
    """Mock admin user (bypasses the ``require_admin`` HTTP guard when
    callers invoke the endpoint handler directly in-process). The
    ``require_admin`` dependency only fires through FastAPI's DI container;
    in-process calls pass ``user`` explicitly and skip the guard."""
    return UsuarioResponse(id=1, nombre="test-admin", is_admin=True)


# ---------------------------------------------------------------------------
# Test 1 — product with U1 stock=5 + bucket=10 → stock_total=15, bucket=10
# ---------------------------------------------------------------------------


async def test_stock_total_combines_physical_and_bucket(
    db_session, estante_factory, producto_factory, ubicacion_factory
):
    """A product with 5 units on a physical cell AND 10 units in the sin
    bucket reports ``stock_total=15`` and ``stock_sin_ubicacion=10``.

    Verifies REQ-B-009 at the API boundary: the invariant
    SUM(physical) + bucket = displayed stock_total holds AFTER Phase C
    (this is the contract ``movimiento_repository.get_producto_stock_total``
    alone does NOT enforce — the endpoint adds the bucket qty here).
    """
    estante_id = await estante_factory(nombre="T1 Shelf")
    sku_p = await producto_factory(sku="T1-P", codigo_de_barra="BAR-T1")
    await ubicacion_factory(
        estante_id=estante_id, fila=1, columna=1, producto_id=sku_p, stock_actual=5
    )
    await _bucket_repo.upsert_add(db_session, sku_p, 10)

    result = await get_producto_stock_total(
        codigo_de_barra="BAR-T1",
        sku=None,  # explicit: bypass the FastAPI Query-FieldInfo default
        db=db_session,
        user=_admin_user(),
    )

    assert result.sku == "T1-P"
    assert result.stock_total == 15
    assert result.stock_sin_ubicacion == 10


# ---------------------------------------------------------------------------
# Test 2 — product without any ubicacion + bucket=8 → stock_total=8
# ---------------------------------------------------------------------------


async def test_stock_total_only_bucket_when_no_physical(
    db_session, producto_factory
):
    """A product whose units ONLY live in the sin-ubicacion bucket (no
    ``ubicaciones`` row, no Suelto movimientos) still reports a non-zero
    ``stock_total`` — equal to the bucket qty — and surfaces the bucket via
    ``stock_sin_ubicacion``. Without the endpoint's correction the user
    would see ``stock_total=0`` while the product demonstrably has units,
    which would violate REQ-B-009.
    """
    sku_p = await producto_factory(sku="T2-P", codigo_de_barra="BAR-T2")
    await _bucket_repo.upsert_add(db_session, sku_p, 8)

    result = await get_producto_stock_total(
        codigo_de_barra="BAR-T2",
        sku=None,  # explicit: bypass the FastAPI Query-FieldInfo default
        db=db_session,
        user=_admin_user(),
    )

    assert result.sku == "T2-P"
    assert result.stock_total == 8
    assert result.stock_sin_ubicacion == 8


# ---------------------------------------------------------------------------
# Test 3 — only physical stock, bucket=0 → stock_total=5, bucket=0
# ---------------------------------------------------------------------------


async def test_stock_total_only_physical_when_bucket_empty(
    db_session, estante_factory, producto_factory, ubicacion_factory
):
    """A product whose units ALL sit on a physical cell (no bucket row, per
    R1 invariant — a missing row == 0 units) reports ``stock_total`` equal
    to the physical sum and ``stock_sin_ubicacion=0`` (default — the
    Pydantic field's ``= 0`` default and the missing-row-from-get_cantidad
    convention agree)."""
    estante_id = await estante_factory(nombre="T3 Shelf")
    sku_p = await producto_factory(sku="T3-P", codigo_de_barra="BAR-T3")
    await ubicacion_factory(
        estante_id=estante_id, fila=1, columna=1, producto_id=sku_p, stock_actual=5
    )
    # No upsert_add → bucket row absent per R1 (no zero-row orphans).

    result = await get_producto_stock_total(
        codigo_de_barra="BAR-T3",
        sku=None,  # explicit: bypass the FastAPI Query-FieldInfo default
        db=db_session,
        user=_admin_user(),
    )

    assert result.sku == "T3-P"
    assert result.stock_total == 5
    assert result.stock_sin_ubicacion == 0


# ---------------------------------------------------------------------------
# Test 4 — GET /sin-ubicacion (admin) lists every bucketed product
# ---------------------------------------------------------------------------


async def test_admin_sin_ubicacion_listing(db_session, producto_factory):
    """``list_stock_sin_ubicacion`` returns one row per product with units
    in the sin-ubicacion bucket, joining ``productos`` for SKU + description.

    Two products pre-populated via :func:`stock_sin_ubicacion_repository.upsert_add`;
    line checks verify the response carries the right ``producto_sku``,
    ``producto_descripcion`` and ``cantidad`` for each. Indexing by sku
    sidesteps the ``updated_at DESC`` / ``producto_id ASC`` ordering
    (both rows share an updated_at within microseconds of one another).
    """
    sku_a = await producto_factory(
        sku="T4-A", descripcion="Alpha product", codigo_de_barra="BAR-T4A"
    )
    sku_b = await producto_factory(
        sku="T4-B", descripcion="Beta product", codigo_de_barra="BAR-T4B"
    )
    await _bucket_repo.upsert_add(db_session, sku_a, 12)
    await _bucket_repo.upsert_add(db_session, sku_b, 7)

    result = await list_stock_sin_ubicacion(
        db=db_session,
        user=_admin_user(),
    )

    assert isinstance(result, list)
    assert len(result) == 2

    # Index by sku for explicit assertions (the ordering is timestamp-major;
    # both rows were written within microseconds of one another in the same
    # test, so the tiebreaker ``producto_id ASC`` may surface first).
    by_sku = {item.producto_sku: item for item in result}
    assert set(by_sku.keys()) == {sku_a, sku_b}

    a = by_sku[sku_a]
    assert a.producto_descripcion == "Alpha product"
    assert a.cantidad == 12
    assert a.updated_at is not None

    b = by_sku[sku_b]
    assert b.producto_descripcion == "Beta product"
    assert b.cantidad == 7
    assert b.updated_at is not None


# ---------------------------------------------------------------------------
# Test 5 — route-registration order sanity: /sin-ubicacion BEFORE /{barcode}
# ---------------------------------------------------------------------------


async def test_sin_ubicacion_route_registered_before_codigo_de_barra_routes():
    """FastAPI matches routes in registration order; if ``/sin-ubicacion``
    were registered AFTER ``/{codigo_de_barra}`` then a GET to
    ``/productos/sin-ubicacion`` would bind ``"sin-ubicacion"`` as the
    ``codigo_de_barra`` value and 404 on the product lookup.

    This test asserts the literal ``/sin-ubicacion`` route exists in the
    router's path list AND appears in the path list BEFORE any
    ``{codigo_de_barra}``-templated single-segment route, so the matcher
    hits the admin listing first.
    """
    # Late import: only inspect the router after the endpoints module has
    # finished registering every route (we don't want a partial view that
    # could race with import-time registration).
    from app.api.v1.endpoints.productos import router

    paths = [route.path for route in router.routes]

    assert "/sin-ubicacion" in paths, (
        "Admin listing route must be registered; without it the literal "
        "'sin-ubicacion' segment cannot resolve"
    )
    sin_ub_index = paths.index("/sin-ubicacion")

    # The two-segment routes ``/{codigo_de_barra}/stock-total`` and
    # ``/{codigo_de_barra}/ubicaciones`` cannot capture a single-segment
    # path, so they don't conflict with ``/sin-ubicacion``. The hazard is
    # the single-segment ``/{codigo_de_barra}`` route (the generic barcode
    # lookup). That one MUST come after ``/sin-ubicacion``.
    barcode_single_paths = [
        idx for idx, p in enumerate(paths)
        if p == "/{codigo_de_barra}"
    ]
    assert barcode_single_paths, (
        "/{codigo_de_barra} route must be registered for barcode lookup"
    )
    barcode_index = barcode_single_paths[0]

    assert sin_ub_index < barcode_index, (
        f"/sin-ubicacion (index {sin_ub_index}) must be registered BEFORE "
        f"/{{codigo_de_barra}} (index {barcode_index}) to prevent the path "
        f"matcher from binding 'sin-ubicacion' as a barcode value"
    )