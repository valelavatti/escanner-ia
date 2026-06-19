import aiosqlite

from app.core.config import get_settings

_CONNECTION_PRAGMAS = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA temp_store = MEMORY;
"""


async def configure_connection(connection: aiosqlite.Connection) -> None:
    """Apply the project-required SQLite pragmas on every connection."""
    await connection.executescript(_CONNECTION_PRAGMAS)


async def get_db_connection(db_path: str) -> aiosqlite.Connection:
    """Open and configure a new SQLite connection."""
    connection = await aiosqlite.connect(db_path, check_same_thread=False)
    connection.row_factory = aiosqlite.Row
    await configure_connection(connection)
    return connection


async def get_db():
    """FastAPI dependency that yields a configured SQLite connection."""
    settings = get_settings()
    async with aiosqlite.connect(settings.db_path, check_same_thread=False) as connection:
        connection.row_factory = aiosqlite.Row
        await configure_connection(connection)
        yield connection
