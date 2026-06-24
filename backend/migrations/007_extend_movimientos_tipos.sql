-- Migration 007: Extend movimientos.tipo to support asignacion and desasignacion.
-- SQLite does not support ALTER TABLE with CHECK modifications, so we recreate the table.

CREATE TABLE movimientos_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    producto_id TEXT,
    ubicacion_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    stock_anterior INTEGER NOT NULL,
    stock_nuevo INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    tipo TEXT NOT NULL CHECK (tipo IN ('alta', 'ajuste', 'asignacion', 'desasignacion')),
    session_id TEXT,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE RESTRICT,
    FOREIGN KEY (producto_id) REFERENCES productos(sku) ON DELETE SET NULL,
    FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones(id) ON DELETE RESTRICT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

-- Copy existing data preserving every column.
INSERT INTO movimientos_new
    (id, usuario_id, producto_id, ubicacion_id, cantidad, stock_anterior, stock_nuevo, timestamp, tipo, session_id)
SELECT id, usuario_id, producto_id, ubicacion_id, cantidad, stock_anterior, stock_nuevo, timestamp, tipo, session_id
FROM movimientos;

-- Swap tables.
DROP TABLE movimientos;
ALTER TABLE movimientos_new RENAME TO movimientos;

-- Recreate original indexes.
CREATE INDEX IF NOT EXISTS idx_movimientos_timestamp ON movimientos(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_movimientos_usuario_id ON movimientos(usuario_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_producto_id ON movimientos(producto_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_ubicacion_id ON movimientos(ubicacion_id);
