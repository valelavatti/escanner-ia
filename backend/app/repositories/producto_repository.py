"""Product data access layer."""

from typing import Optional

import aiosqlite


async def insert_producto(
    db: aiosqlite.Connection,
    sku: str,
    descripcion: str,
    codigo_de_barra: str,
) -> int:
    """Insert a new product. Returns the SQLite rowid."""
    cursor = await db.execute(
        """
        INSERT INTO productos (sku, descripcion, codigo_de_barra)
        VALUES (?, ?, ?)
        """,
        (sku, descripcion, codigo_de_barra),
    )
    return cursor.lastrowid


async def get_producto_by_codigo(
    db: aiosqlite.Connection,
    codigo_de_barra: str,
) -> Optional[dict]:
    """Look up a product by exact barcode."""
    async with db.execute(
        """
        SELECT sku, descripcion, codigo_de_barra, created_at, updated_at
        FROM productos
        WHERE codigo_de_barra = ?
        """,
        (codigo_de_barra,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def get_producto_by_sku(
    db: aiosqlite.Connection,
    sku: str,
) -> Optional[dict]:
    """Look up a product by exact SKU."""
    async with db.execute(
        """
        SELECT sku, descripcion, codigo_de_barra, created_at, updated_at
        FROM productos
        WHERE sku = ?
        """,
        (sku,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def count_productos(db: aiosqlite.Connection) -> int:
    """Return the total number of products in the database."""
    async with db.execute("SELECT COUNT(*) FROM productos") as cursor:
        row = await cursor.fetchone()
        return row[0]


async def search_productos(
    db: aiosqlite.Connection,
    query: str,
    limit: int = 20,
) -> list[dict]:
    """Search products by SKU, description, or barcode using a partial LIKE match."""
    pattern = f"%{query}%"
    async with db.execute(
        """
        SELECT sku, descripcion, codigo_de_barra, created_at
        FROM productos
        WHERE sku LIKE ?
           OR descripcion LIKE ?
           OR codigo_de_barra LIKE ?
        ORDER BY descripcion
        LIMIT ?
        """,
        (pattern, pattern, pattern, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
