-- ============================================================
-- ASG Scanner indexes (Work Unit 2)
-- ============================================================

-- Product lookup (critical for scanner speed and Excel dedup)
CREATE INDEX IF NOT EXISTS idx_productos_codigo_de_barra ON productos(codigo_de_barra);
CREATE INDEX IF NOT EXISTS idx_productos_sku ON productos(sku);

-- Location queries
CREATE INDEX IF NOT EXISTS idx_ubicaciones_estante_id ON ubicaciones(estante_id);
CREATE INDEX IF NOT EXISTS idx_ubicaciones_qr_valor ON ubicaciones(qr_valor);
CREATE INDEX IF NOT EXISTS idx_ubicaciones_producto_id ON ubicaciones(producto_id);

-- Audit trail filtering and sorting
CREATE INDEX IF NOT EXISTS idx_movimientos_timestamp ON movimientos(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_movimientos_usuario_id ON movimientos(usuario_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_producto_id ON movimientos(producto_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_ubicacion_id ON movimientos(ubicacion_id);

-- Session lookups
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

-- Soft-delete filtering: only index active shelves
CREATE INDEX IF NOT EXISTS idx_estantes_deleted_at ON estantes(deleted_at) WHERE deleted_at IS NULL;
