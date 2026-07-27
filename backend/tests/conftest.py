"""In-memory pytest harness for the ASG Scanner backend.

Test isolation strategy
-----------------------
Each test owns a **brand-new in-memory SQLite database** (``:memory:``).
The connection is configured with the same PRAGMAs the production app applies
via :func:`app.core.database.configure_connection` (``foreign_keys = ON``;
``journal_mode = WAL`` is silently downgraded to MEMORY for ``:memory:`` DBs
by SQLite itself — no error, no functional impact). All project migrations
(001-013 as of this slice; 014-016 will be appended by later slices) are
applied via :func:`app.core.migrations.run_migrations`.

Closing a ``:memory:`` connection destroys the database — committed or not.
The :func:`db_session` fixture additionally issues an explicit
``connection.rollback()`` before ``close()`` so any uncommitted transaction
left open by a test (or by production code that wraps writes in
``BEGIN IMMEDIATE`` without a matching ``commit``) is rolled back safely.
Together with the per-test clean-room ``:memory:``, this satisfies the
per-test rollback requirement (REQ-X-004) WITHOUT pre-beginning a wrapping
transaction.

Why no outer ``BEGIN``/``SAVEPOINT`` wrapper
---------------------------------------------
Production code wraps writes in ``conn.execute("BEGIN IMMEDIATE")`` /
``conn.commit()`` (see design R3). If this fixture pre-began a transaction
or SAVEPOINT, calling ``BEGIN IMMEDIATE`` from the production code path
would raise ``cannot start a transaction within a transaction``. The
clean-room ``:memory:`` per test plus ``rollback()`` at teardown yields the
same isolation guarantee a wrapping savepoint would, without colliding with
production's transaction discipline.

Async discovery (``asyncio_mode = auto``)
-----------------------------------------
pytest-asyncio defaults to **strict** mode when no ``pytest.ini`` /
``pyproject.toml`` declares ``asyncio_mode = auto``. Creating an ini file
is out of slice scope (only two files may change in this slice). Instead,
:func:`pytest_configure` sets ``config.option.asyncio_mode = "auto"`` from
the conftest. Since conftest plugins are registered AFTER setuptools entry
points (like pytest-asyncio), this hook runs AFTER pytest-asyncio's own
``pytest_configure`` — and pytest-asyncio's collection logic only reads
the mode LAZILY (via ``_get_asyncio_mode(config)`` at collection time),
so the value we set takes full effect. Subsequent test files (slices 1,
2a, 2b, 3, 4) just declare ``async def test_...`` and pytest-asyncio will
auto-mark them, convert them to its ``Coroutine`` item subclass, and run
them inside the asyncio event loop — no per-test
``@pytest.mark.asyncio`` decoration required.

Test data factories
-------------------
Three async factories (:func:`estante_factory`, :func:`producto_factory`,
:func:`ubicacion_factory`) are provided as fixtures returning async callables.
Test code uses them like:

    estante_id = await estante_factory(nombre="A")
    sku = await producto_factory(sku="SKU-1", codigo_de_barra="111")
    ub_id = await ubicacion_factory(estante_id=estante_id, producto_id=sku)

Each factory commits the inserted row so the test can read it back via plain
``SELECT``; per-test isolation still holds because the ``:memory:`` DB is
destroyed at teardown.
"""

from __future__ import annotations

from typing import Awaitable, Callable

import aiosqlite
import pytest
import pytest_asyncio

from app.core.database import configure_connection
from app.core.migrations import run_migrations


# ---------------------------------------------------------------------------
# Internal builder — fresh in-memory DB with PRAGMAs + all migrations applied.
# ---------------------------------------------------------------------------

async def _build_in_memory_db() -> aiosqlite.Connection:
    """Open a fresh ``:memory:`` SQLite database ready for tests.

    - ``row_factory = aiosqlite.Row`` (matches production ``get_db`` helper).
    - ``configure_connection`` applies the project PRAGMAs.
    - ``run_migrations`` applies every pending migration (001..N) and records
      each in ``schema_migrations``; idempotent so re-calls are skips.

    The caller owns the connection's lifecycle: ``rollback()`` then
    ``close()`` at the end.
    """
    connection = await aiosqlite.connect(":memory:")
    connection.row_factory = aiosqlite.Row
    await configure_connection(connection)
    await run_migrations(connection)
    return connection


# ---------------------------------------------------------------------------
# asyncio_mode = auto (override the strict default without an ini file).
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    """Force pytest-asyncio into ``auto`` mode without requiring an ini file.

    Conftest plugins are registered after entry-point plugins, so this hook
    runs AFTER pytest-asyncio's own :func:`pytest_configure`. pytest-asyncio
    resolves the active mode lazily via :func:`_get_asyncio_mode` at
    collection time, so setting ``config.option.asyncio_mode`` here takes
    effect before any test is collected.

    Effect: every ``async def test_*`` discovered by pytest is automatically
    marked with ``@pytest.mark.asyncio`` and run inside the asyncio loop —
    no per-test decoration needed.
    """
    config.option.asyncio_mode = "auto"


# ---------------------------------------------------------------------------
# Fixtures: in-memory DB factory + per-test db_session.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def in_memory_db() -> Callable[[], Awaitable[aiosqlite.Connection]]:
    """Session-scoped factory that builds a fresh in-memory DB on each call.

    Returns the :func:`_build_in_memory_db` async callable. Each call opens a
    brand-new ``:memory:`` SQLite DB with PRAGMAs applied and all migrations
    run. The fixture itself is sync (so it needs no event loop); only the
    returned callable is awaitable. ``db_session`` (function-scoped) calls the
    factory once per test for clean-room isolation.
    """
    return _build_in_memory_db


@pytest_asyncio.fixture(loop_scope="function")
async def db_session(in_memory_db):
    """Per-test in-memory SQLite connection with all migrations applied.

    Opens a fresh ``:memory:`` DB on each test (clean-room — no shared state
    with any other test in the suite). At teardown we issue ``rollback()`` to
    undo any uncommitted transaction, then ``close()`` to destroy the database
    entirely. No test data can leak to the next test.
    """
    connection = await in_memory_db()
    try:
        yield connection
    finally:
        try:
            await connection.rollback()
        except aiosqlite.Error:
            # No active transaction — closing destroys the DB regardless.
            pass
        await connection.close()


# ---------------------------------------------------------------------------
# Test data factories (async fixtures returning async callables).
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(loop_scope="function")
async def estante_factory(db_session):
    """Insert an ``estantes`` row and return its new ``id``.

    Defaults: a 4x3 shelf named ``"Test Shelf <orden_visual>"``.
    Override any column via keyword args.
    """
    async def _make(
        *,
        nombre: str | None = None,
        filas: int = 4,
        columnas: int = 3,
        orden_visual: int = 0,
        deleted_at: str | None = None,
    ) -> int:
        if nombre is None:
            nombre = f"Test Shelf {orden_visual}"
        cursor = await db_session.execute(
            """
            INSERT INTO estantes
                (nombre, orden_visual, filas, columnas, deleted_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (nombre, orden_visual, filas, columnas, deleted_at),
        )
        await db_session.commit()
        return cursor.lastrowid

    return _make


@pytest_asyncio.fixture(loop_scope="function")
async def producto_factory(db_session):
    """Insert a ``productos`` row and return its ``sku``.

    Defaults: ``sku = "SKU-DEFAULT"``, ``codigo_de_barra = sku`` (both unique).
    """
    async def _make(
        *,
        sku: str | None = None,
        descripcion: str = "Test product",
        codigo_de_barra: str | None = None,
    ) -> str:
        if sku is None:
            sku = "SKU-DEFAULT"
        if codigo_de_barra is None:
            codigo_de_barra = sku
        await db_session.execute(
            "INSERT INTO productos (sku, descripcion, codigo_de_barra) VALUES (?, ?, ?)",
            (sku, descripcion, codigo_de_barra),
        )
        await db_session.commit()
        return sku

    return _make


@pytest_asyncio.fixture(loop_scope="function")
async def ubicacion_factory(db_session, estante_factory):
    """Insert a ``ubicaciones`` row and return its new ``id``.

    If no ``estante_id`` is supplied, a default 4x3 shelf named
    ``"UBFactory Shelf"`` is created via :func:`estante_factory`.
    ``qr_valor`` defaults to ``"UB<estante_id>-F<fila>-C<columna>"`` to stay
    unique within the in-memory DB.
    """
    async def _make(
        *,
        estante_id: int | None = None,
        fila: int = 1,
        columna: int = 1,
        qr_valor: str | None = None,
        producto_id: str | None = None,
        stock_actual: int = 0,
        estado: str = "activo",
    ) -> int:
        if estante_id is None:
            estante_id = await estante_factory(nombre="UBFactory Shelf")
        if qr_valor is None:
            qr_valor = f"UB{estante_id}-F{fila}-C{columna}"
        cursor = await db_session.execute(
            """
            INSERT INTO ubicaciones
                (estante_id, fila, columna, producto_id, stock_actual, qr_valor, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (estante_id, fila, columna, producto_id, stock_actual, qr_valor, estado),
        )
        await db_session.commit()
        return cursor.lastrowid

    return _make