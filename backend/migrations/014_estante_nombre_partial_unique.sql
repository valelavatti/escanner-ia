-- Migration 014: Replace the unconditional UNIQUE constraint on estantes.nombre
-- with a partial unique index that applies ONLY to non-deleted (active) shelves.
--
-- Problem (production bug "ghost shelf"): soft-deleted estantes (deleted_at IS
-- NOT NULL) retain their `nombre`, but the legacy column-level UNIQUE on
-- `estantes.nombre` (from migration 001_create_tables.sql:23, declared as
-- `nombre TEXT UNIQUE NOT NULL`) blocks creation of a NEW active shelf that
-- reuses the same name. Three soft-deleted rows in production (id=2 'A',
-- id=5 'Pasillo 1', id=9 'Estante 1') currently make those names permanently
-- un-recreatable from the admin UI.
--
-- Fix: drop the unconditional UNIQUE column constraint and introduce a PARTIAL
-- unique index `estantes_nombre_active_idx ON estantes(nombre) WHERE deleted_at
-- IS NULL` so uniqueness holds ONLY among active shelves. Soft-deleted ghost
-- rows keep their `nombre` (audit-trail continuity for `movimientos`), but no
-- longer block recreation of an active shelf with the same name.
--
-- Strategy: SQLite cannot ALTER a column's UNIQUE constraint in place, so we
-- use the table-rebuild idiom (precedent: migrations 007 and 012): create
-- `estantes_new` with the same columns EXCEPT the `nombre UNIQUE` clause,
-- copy every existing row (active + ghost) preserving ids and deleted_at,
-- drop the old table, rename, and recreate the indexes that lived on the
-- original `estantes` table.
--
-- PRAGMA discipline: `PRAGMA foreign_keys = OFF` is required for the duration
-- of the rebuild because `ubicaciones.estante_id REFERENCES estantes(id) ON
-- DELETE RESTRICT` (migration 001:46) would otherwise block `DROP TABLE
-- estantes`. `PRAGMA foreign_keys` may only be toggled OUTSIDE a pending
-- transaction, so the script structure is:
--   1. PRAGMA foreign_keys = OFF;     -- outside any tx (executescript pre-commits)
--   2. BEGIN; ... rebuild ... COMMIT; -- single atomic transaction; FK enforcement
--                                     -- is suspended for the table swap
--   3. PRAGMA foreign_keys = ON;      -- outside any tx after COMMIT, restoring
--                                     -- the connection's FK setting
-- If the rebuild fails mid-block, the BEGIN/COMMIT rolls back the entire swap;
-- the connection's FK setting is re-applied by `core.database.configure_connection`
-- on the next connection acquisition (production) or by the per-test clean-room
-- `:memory:` reset of `db_session` (tests). The migration is retried on re-run
-- because the runner only records `schema_migrations` rows for migrations that
-- succeed (see `app/core/migrations.py:run_migrations`).
--
-- Spec anchors: REQ-A-001, A-002, A-003, A-004, A-005, A-006, A-007, A-008.

PRAGMA foreign_keys = OFF;

BEGIN;

-- New `estantes` table with NO UNIQUE on `nombre`. Column order matches the
-- legacy schema after migrations 005 (added `deposito_id`) and 013 (added the
-- four label-config columns), so the explicit-column-list INSERT below copies
-- every column by name (safe against future re-orders).
CREATE TABLE estantes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    orden_visual INTEGER NOT NULL DEFAULT 0,
    filas INTEGER NOT NULL CHECK (filas > 0),
    columnas INTEGER NOT NULL CHECK (columnas > 0),
    deleted_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deposito_id INTEGER REFERENCES depositos(id),
    fila_order TEXT NOT NULL DEFAULT 'top_down',
    columna_order TEXT NOT NULL DEFAULT 'left_right',
    fila_format TEXT NOT NULL DEFAULT 'numeric',
    columna_format TEXT NOT NULL DEFAULT 'numeric'
);

-- Copy every existing row (active + soft-deleted ghost) preserving ids,
-- soft-delete timestamps, deposito FK, and label config. Ghost rows are NOT
-- modified (REQ-A-005: id=2 'A', id=5 'Pasillo 1', id=9 'Estante 1' in prod
-- remain soft-deleted with their data intact).
INSERT INTO estantes_new
    (id, nombre, orden_visual, filas, columnas, deleted_at, created_at,
     deposito_id, fila_order, columna_order, fila_format, columna_format)
SELECT
    id, nombre, orden_visual, filas, columnas, deleted_at, created_at,
    deposito_id, fila_order, columna_order, fila_format, columna_format
FROM estantes;

-- Swap the tables. All indexes on `estantes` (the soft-delete filter index
-- `idx_estantes_deleted_at` from migration 002, plus the implicit auto-index
-- `sqlite_autoindex_estantes_1` backing the legacy `nombre UNIQUE` constraint)
-- are dropped together with the table.
DROP TABLE estantes;
ALTER TABLE estantes_new RENAME TO estantes;

-- New partial unique index: shelf names must be unique ONLY among ACTIVE
-- shelves (deleted_at IS NULL). This is the surgical replacement for the
-- unconditional `nombre UNIQUE` column constraint from migration 001. Ghost
-- rows keep their name (audit-trail preservation) but no longer block
-- recreation (REQ-A-001..004).
CREATE UNIQUE INDEX estantes_nombre_active_idx
    ON estantes(nombre) WHERE deleted_at IS NULL;

-- Recreate the soft-delete filter partial index from migration 002 (its
-- definition matches the original: partial, only where active).
CREATE INDEX IF NOT EXISTS idx_estantes_deleted_at
    ON estantes(deleted_at) WHERE deleted_at IS NULL;

COMMIT;

PRAGMA foreign_keys = ON;