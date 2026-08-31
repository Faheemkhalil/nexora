"""Pytest configuration and fixtures."""
import pytest
import asyncio
import tempfile
from pathlib import Path

# Configure pytest-asyncio
pytest_asyncio_mode = "auto"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def temp_data_dir(monkeypatch):
    """Use temporary directory for data storage during tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Patch database path
        import app.core.db as db_module
        original_db_path = db_module._DB_PATH
        db_module._DB_PATH = tmp_path / "nexora.db"
        db_module._pool = None

        # Patch secrets fallback directory
        import app.core.secrets as secrets_module
        original_secrets_dir = secrets_module._FALLBACK_DIR
        original_secrets_file = secrets_module._FALLBACK_FILE
        original_use_fallback = secrets_module._use_fallback
        secrets_module._FALLBACK_DIR = tmp_path
        secrets_module._FALLBACK_FILE = tmp_path / "secrets.json"
        secrets_module._use_fallback = False

        yield tmp_path

        # Restore
        db_module._DB_PATH = original_db_path
        db_module._pool = None
        secrets_module._FALLBACK_DIR = original_secrets_dir
        secrets_module._FALLBACK_FILE = original_secrets_file
        secrets_module._use_fallback = original_use_fallback