from pathlib import Path

import aiosqlite

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_MIGRATIONS_DIR = _BACKEND_DIR / "migrations"


def _load_migration(name: str) -> str:
    path = _MIGRATIONS_DIR / name
    return path.read_text(encoding="utf-8")


# Versioned migrations: (version, name, sql_script).
MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "create_tables", _load_migration("001_create_tables.sql")),
    (2, "create_indexes", _load_migration("002_create_indexes.sql")),
    (3, "seed_users", _load_migration("003_seed_users.sql")),
    (4, "seed_suelto_shelf", _load_migration("004_seed_suelto_shelf.sql")),
    (5, "create_depositos", _load_migration("005_create_depositos.sql")),
    (6, "seed_deposito_central", _load_migration("006_seed_deposito_central.sql")),
    (7, "extend_movimientos_tipos", _load_migration("007_extend_movimientos_tipos.sql")),
    (8, "add_stock_general_columns", _load_migration("008_add_stock_general_columns.sql")),
    (9, "add_password_and_admin_to_usuarios", _load_migration("009_add_password_and_admin_to_usuarios.sql")),
    (10, "create_usuario_deposito", _load_migration("010_create_usuario_deposito.sql")),
    (11, "seed_admin_permissions", _load_migration("011_seed_admin_permissions.sql")),
]


async def run_migrations(connection: aiosqlite.Connection) -> None:
    """Execute pending migrations in order.

    Safe to call multiple times: already applied migrations are skipped.
    """
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await connection.commit()

    cursor = await connection.execute(
        "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
    )
    row = await cursor.fetchone()
    current_version = row[0] if row else 0
    await cursor.close()

    for version, name, sql in MIGRATIONS:
        if version <= current_version:
            continue

        await connection.executescript(sql)
        await connection.execute(
            "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
            (version, name),
        )
        await connection.commit()
