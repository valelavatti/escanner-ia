-- Migration 010: Create usuario_deposito junction table for per-deposito roles.
CREATE TABLE IF NOT EXISTS usuario_deposito (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    deposito_id INTEGER NOT NULL REFERENCES depositos(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'operator', 'viewer')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (usuario_id, deposito_id)
);

CREATE INDEX IF NOT EXISTS idx_usuario_deposito_usuario ON usuario_deposito(usuario_id);
CREATE INDEX IF NOT EXISTS idx_usuario_deposito_deposito ON usuario_deposito(deposito_id);
