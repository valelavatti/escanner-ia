-- Migration 004: Seed the catch-all "Suelto" shelf for products without a physical location.
-- This estante has filas=1, columnas=1, so it generates a single ubicacion.
-- QR value is just "Suelto" (single-position shelf per the adaptive QR format).

INSERT INTO estantes (nombre, orden_visual, filas, columnas)
VALUES ('Suelto', 0, 1, 1);

-- Generate the single ubicacion for the Suelto shelf.
INSERT INTO ubicaciones (estante_id, fila, columna, producto_id, stock_actual, qr_valor)
SELECT id, 1, 1, NULL, 0, 'Suelto'
FROM estantes
WHERE nombre = 'Suelto' AND deleted_at IS NULL;
