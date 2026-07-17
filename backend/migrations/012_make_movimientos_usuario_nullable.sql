-- Migration 012: Make movimientos.usuario_id nullable so users can be deleted.
--
-- Problem: movimientos.usuario_id was NOT NULL with ON DELETE RESTRICT, so
-- deleting a user who had any stock movements raised a FOREIGN KEY constraint
-- error (500). Movimientos are an append-only audit trail — we must NOT delete
-- them, but we CAN anonymize the user reference (set usuario_id = NULL) to
-- preserve the audit record while allowing user deletion.
--
-- SQLite does not support ALTER TABLE ... ALTER COLUMN, so we recreate the
-- table with usuario_id as nullable and the FK changed to ON DELETE SET NULL
-- (safety net — the repository also nullifies usuario_id explicitly before
-- the DELETE so the intent is clear even if FK enforcement is off).
--
-- All existing columns and data are preserved.

CREATE TABLE movimientos_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    producto_id TEXT,
    ubicacion_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    stock_anterior INTEGER NOT NULL,
    stock_nuevo INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    tipo TEXT NOT NULL CHECK (tipo IN ('alta', 'ajuste', 'asignacion', 'desasignacion')),
    session_id TEXT,
    stock_general_anterior INTEGER DEFAULT 0,
    stock_general_nuevo INTEGER DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    FOREIGN KEY (producto_id) REFERENCES productos(sku) ON DELETE SET NULL,
    FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones(id) ON DELETE RESTRICT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

-- Copy all existing data preserving every column.
INSERT INTO movimientos_new
    (id, usuario_id, producto_id, ubicacion_id, cantidad, stock_anterior,
     stock_nuevo, timestamp, tipo, session_id, stock_general_anterior,
     stock_general_nuevo)
SELECT id, usuario_id, producto_id, ubicacion_id, cantidad, stock_anterior,
       stock_nuevo, timestamp, tipo, session_id, stock_general_anterior,
       stock_general_nuevo
FROM movimientos;

-- Swap tables.
DROP TABLE movimientos;
ALTER TABLE movimientos_new RENAME TO movimientos;

-- Recreate original indexes.
CREATE INDEX IF NOT EXISTS idx_movimientos_timestamp ON movimientos(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_movimientos_usuario_id ON movimientos(usuario_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_producto_id ON movimientos(producto_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_ubicacion_id ON movimientos(ubicacion_id);
