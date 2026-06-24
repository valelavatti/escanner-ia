-- Migration 008: Add stock_general columns to movimientos so every record captures
-- the product's total stock snapshot at that moment.
ALTER TABLE movimientos ADD COLUMN stock_general_anterior INTEGER DEFAULT 0;
ALTER TABLE movimientos ADD COLUMN stock_general_nuevo INTEGER DEFAULT 0;
