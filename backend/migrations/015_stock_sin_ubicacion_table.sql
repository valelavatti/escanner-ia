-- Migration 015: Create the `stock_sin_ubicacion` table — the "sin-ubicacion
-- bucket".
--
-- The scanner tracks THREE stock dimensions per product (REQ-X-001):
--   1) `stock_general`       — total product stock across the warehouse.
--                              Computed on demand (no table): SUM(ubicaciones
--                              .stock_actual) for the product on regular
--                              shelves + SUM(movimientos.cantidad) for the
--                              product on Suelto shelves. See
--                              `movimiento_repository.get_producto_stock_total`.
--   2) `ubicaciones.stock_actual` — per-LOCATION stock; one row per physical
--                                   cell (Suelto is a real 1x1 ubicacion).
--   3) `stock_sin_ubicacion.cantidad` — the SIN UBICACION BUCKET. Units that
--                                       were un-assigned from a cell (an admin
--                                       cancels an assignment, or a cell is
--                                       reassigned to a different product while
--                                       still holding units of the original
--                                       product). They have no physical home
--                                       YET; they wait in the bucket until the
--                                       next `assign` flow that re-targets the
--                                       same product "rescues" them (see the
--                                       `rescate_sin_ubicacion` movimiento tipo
--                                       introduced by migration 016).
--
-- The bucket is NEVER a row in `ubicaciones` (no sentinel QR, no overlap with
-- Suelto). Discrimination between a Suelto ubicacion and the sin-ubicacion
-- bucket happens at the QUERY layer, not the data layer: Suelto shows up via
-- its real `ubicaciones` row (ubicacion_id = 1, qr_valor = 'Suelto'); the
-- bucket shows up via a synthetic UNION branch (ubicacion_id = NULL, label =
-- 'SIN UBICACION'). Suelto is a PHYSICAL storage modality (loose units in a
-- bin); the bucket is a TRANSIT state (bookkeeping for units that lost their
-- physical cell).
--
-- R1 INVARIANT — DELETE-row-on-zero
-- --------------------------------
-- When `stock_sin_ubicacion.cantidad` reaches 0 (via drain() or
-- delete_if_zero()), the row is REMOVED. A row in this table ALWAYS means
-- "there IS bucket stock for this product": the presence predicate
-- EXISTS(SELECT 1 FROM stock_sin_ubicacion WHERE producto_id = ?) is the same
-- as the cantidad > 0 predicate. This keeps every consumer free of
-- `WHERE cantidad > 0` filters.
--
-- The primary key is `producto_id` (one bucket row per product). The FK to
-- `productos(sku)` cascades on product deletion so a deleted product's bucket
-- residual does not dangle.
--
-- Spec anchors: REQ-B-002, REQ-B-004, REQ-B-005, REQ-B-006, REQ-B-007,
-- REQ-C-001, REQ-X-001, R1.

CREATE TABLE IF NOT EXISTS stock_sin_ubicacion (
    producto_id TEXT PRIMARY KEY REFERENCES productos(sku) ON DELETE CASCADE,
    cantidad INTEGER NOT NULL DEFAULT 0 CHECK (cantidad >= 0),
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- The PRIMARY KEY is already covered by SQLite's automatic
-- `sqlite_autoindex_stock_sin_ubicacion_1`, so a separate lookup index on
-- `producto_id` is redundant. Per design #296 §2, no additional index is
-- created.