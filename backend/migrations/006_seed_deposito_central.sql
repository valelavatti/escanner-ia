-- Migration 006: Seed default deposito and assign existing estantes.
INSERT OR IGNORE INTO depositos (id, nombre) VALUES (1, 'Depósito Central');

-- Assign all existing estantes to Depósito Central (excluding soft-deleted).
UPDATE estantes
SET deposito_id = 1
WHERE deleted_at IS NULL AND deposito_id IS NULL;
