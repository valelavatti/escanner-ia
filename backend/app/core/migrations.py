from typing import Iterable

import aiosqlite

# Versioned migrations: (version, name, sql_script).
# Work Unit 2 will populate the first schema migration.
MIGRATIONS: list[tuple[int, str, str]] = []


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
