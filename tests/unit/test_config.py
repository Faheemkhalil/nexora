"""Unit tests for configuration."""
import os
import tempfile
from pathlib import Path

from app.core.config import (
    Settings,
    ServerSettings,
    SecuritySettings,
    UISettings,
    AIGlobals,
    DatabaseSettings,
)


def test_server_settings_defaults():
    """Test ServerSettings defaults."""
    cfg = ServerSettings()
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8765


def test_security_settings_defaults():
    """Test SecuritySettings defaults."""
    cfg = SecuritySettings()
    assert cfg.local_only is False
    assert cfg.conversation_storage is True
    assert cfg.secure_logging is True


def test_ui_settings_defaults():
    """Test UISettings defaults."""
    cfg = UISettings()
    assert cfg.theme == "dark"
    assert cfg.fullscreen is False
    assert cfg.reduced_motion is False


def test_ai_globals_defaults():
    """Test AIGlobals defaults."""
    cfg = AIGlobals()
    assert cfg.default_temperature == 0.7
    assert cfg.default_context == 4096
    assert cfg.streaming is True
    assert cfg.offline_fallback_enabled is True


def test_database_settings_path():
    """Test DatabaseSettings path resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = DatabaseSettings(path=Path(tmpdir) / "test.db")
        assert cfg.path.name == "test.db"


def test_settings_nested():
    """Test Settings with nested configs."""
    settings = Settings()
    assert isinstance(settings.server, ServerSettings)
    assert isinstance(settings.security, SecuritySettings)
    assert isinstance(settings.ui, UISettings)
    assert isinstance(settings.ai, AIGlobals)
    assert isinstance(settings.database, DatabaseSettings)


def test_settings_env_override(monkeypatch):
    """Test environment variable overrides."""
    monkeypatch.setenv("SERVER__HOST", "0.0.0.0")
    monkeypatch.setenv("SERVER__PORT", "9000")
    monkeypatch.setenv("AI__DEFAULT_TEMPERATURE", "0.5")

    settings = Settings()
    assert settings.server.host == "0.0.0.0"
    assert settings.server.port == 9000
    assert settings.ai.default_temperature == 0.5