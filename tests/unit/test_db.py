"""Unit tests for database module."""
import pytest
import tempfile
import asyncio
from pathlib import Path

from app.core.db import init_db, execute


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        # Override the database path
        import app.core.db as db_module
        original_path = db_module._DB_PATH
        db_module._DB_PATH = db_path
        db_module._pool = None

        async def run_init():
            await init_db()

        asyncio.run(run_init())

        yield db_path

        # Restore
        db_module._DB_PATH = original_path
        db_module._pool = None


def test_database_init(temp_db):
    """Test database initialization creates tables."""
    async def run():
        tables = await execute(
            "SELECT name FROM sqlite_master WHERE type='table'", fetch="all"
        )
        table_names = {t["name"] for t in tables}
        expected = {
            "settings",
            "providers",
            "conversations",
            "messages",
            "findings",
            "audit_logs",
            "memory",
            "tasks",
        }
        assert expected.issubset(table_names)
    asyncio.run(run())


def test_execute_insert_select(temp_db):
    """Test basic insert and select."""
    async def run():
        await execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("test_key", "test_value"),
        )
        result = await execute(
            "SELECT value FROM settings WHERE key = ?", ("test_key",), fetch="one"
        )
        assert result["value"] == "test_value"
    asyncio.run(run())


def test_execute_fetch_all(temp_db):
    """Test fetch all."""
    async def run():
        await execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("k1", "v1"))
        await execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("k2", "v2"))
        results = await execute("SELECT key, value FROM settings ORDER BY key", fetch="all")
        assert len(results) == 2
        assert results[0]["key"] == "k1"
        assert results[1]["key"] == "k2"
    asyncio.run(run())


def test_migrations_table(temp_db):
    """Test migrations table exists and has entries."""
    async def run():
        # The migrations table is tracked via a separate schema_version file
        # not a database table. Verify schema_version file exists.
        import app.core.db as db_module
        version_path = db_module._DB_PATH.with_suffix(
            db_module._DB_PATH.suffix + ".schema_version"
        )
        assert version_path.exists()
        version = int(version_path.read_text().strip())
        assert version == 9
    asyncio.run(run())


def test_providers_table(temp_db):
    """Test providers table structure."""
    async def run():
        await execute(
            """INSERT INTO providers (id, type, name, model, base_url, extra, configured, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("test-prov", "openrouter", "Test", "gpt-4", None, None, True, 123, 123),
        )
        result = await execute(
            "SELECT * FROM providers WHERE id = ?", ("test-prov",), fetch="one"
        )
        assert result["id"] == "test-prov"
        assert result["type"] == "openrouter"
        assert result["configured"] == 1
    asyncio.run(run())