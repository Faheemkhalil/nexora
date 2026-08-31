"""Async SQLite database with migration support."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import aiosqlite
from loguru import logger

from .config import settings
from .errors import DatabaseError

_DB_PATH = settings.database.path


async def init_db(db_path: Path | None = None) -> None:
    """Initialize database: create directory, run migrations."""
    path = db_path or _DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    await _run_migrations(path)


_MIGRATIONS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id          TEXT PRIMARY KEY,
        title       TEXT NOT NULL,
        provider_id TEXT NOT NULL,
        model       TEXT NOT NULL,
        created_at  REAL NOT NULL,
        updated_at  REAL NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id             TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL,
        role           TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
        content        TEXT NOT NULL,
        provider       TEXT,
        model          TEXT,
        created_at     REAL NOT NULL,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS providers (
        id          TEXT PRIMARY KEY,
        type        TEXT NOT NULL,
        name        TEXT NOT NULL,
        configured  INTEGER NOT NULL DEFAULT 0,
        model       TEXT NOT NULL,
        base_url    TEXT,
        extra       TEXT,
        created_at  REAL NOT NULL,
        updated_at  REAL NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id          TEXT PRIMARY KEY,
        action      TEXT NOT NULL,
        resource    TEXT,
        outcome     TEXT NOT NULL CHECK(outcome IN ('success', 'failure', 'denied')),
        details     TEXT,
        user_id     TEXT,
        timestamp   REAL NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS findings (
        id          TEXT PRIMARY KEY,
        title       TEXT NOT NULL,
        severity    TEXT NOT NULL CHECK(severity IN ('critical', 'high', 'medium', 'low', 'informational')),
        asset       TEXT NOT NULL,
        description TEXT NOT NULL,
        evidence    TEXT,
        impact      TEXT,
        remediation TEXT,
        refs        TEXT,
        timestamp   REAL NOT NULL,
        resolved    INTEGER NOT NULL DEFAULT 0
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS memory (
        id          TEXT PRIMARY KEY,
        scope       TEXT NOT NULL CHECK(scope IN ('global', 'project', 'conversation')),
        key         TEXT NOT NULL,
        value       TEXT NOT NULL,
        created_at  REAL NOT NULL,
        updated_at  REAL NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id          TEXT PRIMARY KEY,
        title       TEXT NOT NULL,
        description TEXT,
        status      TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'blocked')),
        conversation_id TEXT,
        created_at  REAL NOT NULL,
        updated_at  REAL NOT NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
    CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
    CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
    CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory(scope);
    """,
]


async def _run_migrations(db_path: Path) -> None:
    """Run database migrations, tracking schema version."""
    version_path = db_path.with_suffix(db_path.suffix + ".schema_version")
    current_version = 0
    if version_path.exists():
        current_version = int(version_path.read_text().strip())

    needed = _MIGRATIONS[current_version:]
    if not needed:
        return

    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        for i, migration in enumerate(needed, start=current_version):
            try:
                await db.executescript(migration)
                logger.debug(f"Migration {i + 1} applied successfully.")
            except Exception as e:
                await db.rollback()
                raise DatabaseError(f"Migration {i + 1} failed.", details=str(e))
        await db.commit()

    version_path.write_text(str(len(_MIGRATIONS)))
    logger.info(f"Database migrations complete. {_DB_PATH} — {len(_MIGRATIONS)} version(s).")


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager yielding a database connection."""
    try:
        db = aiosqlite.connect(str(_DB_PATH))
        conn = await db
        conn.row_factory = aiosqlite.Row
        yield conn
        await conn.close()
    except Exception as e:
        raise DatabaseError("Database connection failed.", details=str(e))


async def execute(query: str, params: tuple | None = None, *, fetch: str = "none") -> Any:
    """Execute a query with optional parameter binding.

    fetch: 'none' (commit and return None), 'one' (fetchone), 'all' (fetchall)
    """
    try:
        async with get_db() as db:
            if params is None:
                cursor = await db.execute(query)
            else:
                cursor = await db.execute(query, params)
            if fetch == "one":
                row = await cursor.fetchone()
                await cursor.close()
                return dict(row) if row else None
            if fetch == "all":
                rows = await cursor.fetchall()
                await cursor.close()
                return [dict(r) for r in rows]
            await cursor.close()
            await db.commit()
            return None
    except aiosqlite.Error as e:
        raise DatabaseError("Database query failed.", details=str(e))
