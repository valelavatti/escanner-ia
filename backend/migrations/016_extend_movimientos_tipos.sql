-- Migration 016: Extend the CHECK constraint on `movimientos.tipo` to accept
-- two new literals:
--   1) 'rescate_sin_ubicacion' — written by
--      `movimiento_repository.create_movimiento_rescate_sin_ubicacion` when an
--      `assign_producto_to_ubicacion` flow drains qty FROM the
--      `stock_sin_ubicacion` bucket INTO a real ubicacion (REQ-B-006, B-007).
--   2) 'salvage_cleanup'       — written by
--      `movimiento_repository.create_movimiento_salvage_cleanup` (and the
--      `backfill_orphans.py` script) to record the cleanup of orphan ubicacion
--      stock (ubicaciones with stock_actual > 0 AND producto_id IS NULL);
--      `producto_id` is intentionally NULL on these rows (REQ-D-002, D-003).
--
-- SQLite cannot ALTER a column's CHECK constraint in place, so we use the
-- table-rebuild idiom (precedent: migrations 007 — added 'asignacion' and
-- 'desasignacion' — and 012 — made `usuario_id` nullable). The new schema
-- MUST match the post-012 schema (usuario_id nullable + FK ON DELETE SET NULL on
-- usuario_id + stock_general_anterior/stock_general_nuevo from migration 008)
-- with the ONLY change being the extended CHECK list. All existing rows are
-- preserved — the INSERT-by-explicit-column-list copies every existing column
-- (12 columns total: 10 from migration 001 + 2 from migration 008).
--
-- PRAGMA foreign_keys = OFF is NOT required. `movimientos` is the FK TARGET
-- (no other table in this schema references `movimientos` directly). Dropping
-- the table drops only the table definition; the FKs we declare ON
-- `movimientos` here point FROM movimientos INTO
-- usuarios / productos / ubicaciones / sessions (not the other way around), so
-- DROP TABLE is safe with FK enforcement ON. Precedent: migrations 007 and 012
-- both rebuilt `movimientos` WITHOUT a PRAGMA foreign_keys toggle.
--
-- Spec anchors: REQ-B-006, REQ-B-007, REQ-D-002, REQ-D-003, R2.

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
        -- NEW literals added by this migration (Slice 2a):
        'rescate_sin_ubicacion',
        'salvage_cleanup'
    )),
    session_id TEXT,
    stock_general_anterior INTEGER DEFAULT 0,
    stock_general_nuevo INTEGER DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    FOREIGN KEY (producto_id) REFERENCES productos(sku) ON DELETE SET NULL,
    FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones(id) ON DELETE RESTRICT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

-- Copy every existing row preserving all 12 columns
-- (10 from migration 001 + 2 added by migration 008). The explicit column
-- list is safe against future re-orders and refuses to silently drop columns
-- if the source schema diverges.
INSERT INTO movimientos_new
    (id, usuario_id, producto_id, ubicacion_id, cantidad, stock_anterior,
     stock_nuevo, timestamp, tipo, session_id, stock_general_anterior,
     stock_general_nuevo)
SELECT id, usuario_id, producto_id, ubicacion_id, cantidad, stock_anterior,
       stock_nuevo, timestamp, tipo, session_id, stock_general_anterior,
       stock_general_nuevo
FROM movimientos;

-- Swap tables. The 4 original indexes (recreated by migrations 002, 007, and
-- 012) are dropped together with the table by `DROP TABLE movimientos`.
DROP TABLE movimientos;
ALTER TABLE movimientos_new RENAME TO movimientos;

-- Recreate the 4 original indexes (one per FK / hot lookup dimension).
CREATE INDEX IF NOT EXISTS idx_movimientos_timestamp ON movimientos(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_movimientos_usuario_id ON movimientos(usuario_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_producto_id ON movimientos(producto_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_ubicacion_id ON movimientos(ubicacion_id);