-- Migration 005: Create depositos (warehouses) table and link estantes.
CREATE TABLE IF NOT EXISTS depositos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Add nullable FK to estantes (existing estantes without deposito stay NULL).
ALTER TABLE estantes ADD COLUMN deposito_id INTEGER REFERENCES depositos(id);
