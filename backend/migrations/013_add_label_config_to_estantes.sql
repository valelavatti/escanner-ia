-- Migration 013: Per-estante label configuration (direction and format per axis).
-- Defaults reproduce the historic labeling (rows top-down, columns left-right,
-- both numeric) so existing estantes keep their current QR labels.
ALTER TABLE estantes ADD COLUMN fila_order TEXT NOT NULL DEFAULT 'top_down';
ALTER TABLE estantes ADD COLUMN columna_order TEXT NOT NULL DEFAULT 'left_right';
ALTER TABLE estantes ADD COLUMN fila_format TEXT NOT NULL DEFAULT 'numeric';
ALTER TABLE estantes ADD COLUMN columna_format TEXT NOT NULL DEFAULT 'numeric';
