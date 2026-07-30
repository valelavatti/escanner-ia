-- Migration 017: Add TWO new audit-snapshot columns to `movimientos` so the
-- historial can show "Sin ubicación: anterior → nuevo" alongside "Stock
-- general: anterior → nuevo".
--
--   * `stock_sin_ubicacion_anterior INTEGER NOT NULL DEFAULT 0`
--   * `stock_sin_ubicacion_nuevo    INTEGER NOT NULL DEFAULT 0`
--
-- These columns capture the PRODUCT's `stock_sin_ubicacion` bucket qty
-- BEFORE and AFTER the audit-row's event (e.g. a rescate row shows the
-- bucket shrinking by `drain_bucket_qty`; a desasignacion row shows the
-- OLD product's bucket growing by the freed ubicacion qty; an alta row
-- shows the bucket shrinking if the alta drained bucket units, etc).
-- Historical rows (written before this migration existed) get DEFAULT 0
-- for both columns — the historical "Sin ubicación" snapshot is unknown
-- for those rows, which is the accepted limitation until such rows age
-- out of the active audit window.
--
-- SQLite cannot ALTER ADD COLUMN with NOT NULL safely (the DEFAULT 0 is
-- honored, but mixing table-rebuild with explicit NULL inserts would
-- trip the NOT NULL constraint). We use the table-rebuild idiom from
-- migration 016 (and 007, 012 before it): CREATE movimientos_new with
-- the EXTENDED schema + CHECK constraint (preserved verb-atim from
-- migration 016's rebuilt shape) + the two new columns; INSERT-row-by-row
-- every existing row by explicit column list (omitting the two new
-- columns so SQLite honors NOT NULL DEFAULT 0 for them); DROP the old
-- table; RENAME new → movimientos; recreate the 4 original indexes.
-- PRAGMA foreign_keys = OFF is NOT required (the precedent in
-- migrations 007, 012, and 016 all confirmed this: `movimientos` is the
-- FK source, not target — nothing else references it).
--
-- Spec anchors: Slice 8 — Bug 1 + Feature (stock_general includes
-- bucket; drain manualized via `drain_bucket_qty`; historial exposes the
-- bucket delta per movimiento).

CREATE TABLE movimientos_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    producto_id TEXT,
    ubicacion_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    stock_anterior INTEGER NOT NULL,
    stock_nuevo INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    tipo TEXT NOT NULL CHECK (tipo IN (
        -- Original 4 literals (preserved by migrations 007 + 012):
        'alta',
        'ajuste',
        'asignacion',
        'desasignacion',
        -- Added by migration 016 (Slice 2a):
        'rescate_sin_ubicacion',
        'salvage_cleanup'
    )),
    session_id TEXT,
    stock_general_anterior INTEGER DEFAULT 0,
    stock_general_nuevo INTEGER DEFAULT 0,
    -- NEW Slice 8 columns: bucket qty snapshots per audit row.
    stock_sin_ubicacion_anterior INTEGER NOT NULL DEFAULT 0,
    stock_sin_ubicacion_nuevo INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    FOREIGN KEY (producto_id) REFERENCES productos(sku) ON DELETE SET NULL,
    FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones(id) ON DELETE RESTRICT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

-- Copy every existing column (the 12 columns established by migration
-- 001 + 008 + 012 + 016). The two NEW columns are INTENTIONALLY OMITTED
-- from the explicit column list so SQLite applies NOT NULL DEFAULT 0 for
-- every historical row (NOT NULL would trip on explicit NULL — see the
-- migration header). Explicit column list is also a stable guard against
-- silent column re-orderings in the source schema.
INSERT INTO movimientos_new
    (id, usuario_id, producto_id, ubicacion_id, cantidad, stock_anterior,
     stock_nuevo, timestamp, tipo, session_id, stock_general_anterior,
     stock_general_nuevo)
SELECT id, usuario_id, producto_id, ubicacion_id, cantidad, stock_anterior,
       stock_nuevo, timestamp, tipo, session_id, stock_general_anterior,
       stock_general_nuevo
FROM movimientos;

-- Swap tables. The 4 original indexes are dropped together with the
-- table by `DROP TABLE movimientos` (precedent: migration 016).
DROP TABLE movimientos;
ALTER TABLE movimientos_new RENAME TO movimientos;

-- Recreate the 4 original indexes (one per FK / hot lookup dimension).
-- Precedent: migrations 002, 007, 012, 016.
CREATE INDEX IF NOT EXISTS idx_movimientos_timestamp ON movimientos(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_movimientos_usuario_id ON movimientos(usuario_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_producto_id ON movimientos(producto_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_ubicacion_id ON movimientos(ubicacion_id);