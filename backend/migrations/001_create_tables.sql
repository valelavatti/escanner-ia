-- ============================================================
-- ASG Scanner core schema (Work Unit 2)
-- ============================================================

-- ------------------------------------------------------------
-- productos
-- SKU is the natural primary key; barcode is the scan key.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS productos (
    sku TEXT PRIMARY KEY,
    descripcion TEXT NOT NULL,
    codigo_de_barra TEXT UNIQUE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- estantes
-- Soft delete via deleted_at preserves audit history.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS estantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    orden_visual INTEGER NOT NULL DEFAULT 0,
    filas INTEGER NOT NULL CHECK (filas > 0),
    columnas INTEGER NOT NULL CHECK (columnas > 0),
    deleted_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- ubicaciones
-- Each shelf cell. estado allows flagging out-of-bounds cells.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ubicaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estante_id INTEGER NOT NULL,
    fila INTEGER NOT NULL CHECK (fila > 0),
    columna INTEGER NOT NULL CHECK (columna > 0),
    producto_id TEXT,
    stock_actual INTEGER NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
    qr_valor TEXT UNIQUE NOT NULL,
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'fuera_de_rango')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (estante_id) REFERENCES estantes(id) ON DELETE RESTRICT,
    FOREIGN KEY (producto_id) REFERENCES productos(sku) ON DELETE SET NULL,
    UNIQUE (estante_id, fila, columna)
);

-- ------------------------------------------------------------
-- usuarios
-- Simple user list for audit attribution.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login_at DATETIME
);

-- ------------------------------------------------------------
-- sessions
-- Server-side session store. id is the session token itself.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- movimientos
-- Append-only audit trail. No UPDATE or DELETE APIs will exist.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    producto_id TEXT,
    ubicacion_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    stock_anterior INTEGER NOT NULL,
    stock_nuevo INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    tipo TEXT NOT NULL CHECK (tipo IN ('alta', 'ajuste')),
    session_id TEXT,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE RESTRICT,
    FOREIGN KEY (producto_id) REFERENCES productos(sku) ON DELETE SET NULL,
    FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones(id) ON DELETE RESTRICT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);
