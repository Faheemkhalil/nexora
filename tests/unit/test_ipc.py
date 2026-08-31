"""Unit tests for IPC module."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.ipc import IPCServer


@pytest.fixture
def ipc_server():
    """Create an IPCServer instance."""
    with patch("app.ipc.settings") as mock_settings:
        mock_settings.server.host = "127.0.0.1"
        mock_settings.server.port = 8765
        server = IPCServer()
        yield server


def test_ipc_server_creation(ipc_server):
    """Test IPCServer creation."""
    assert ipc_server._app is not None
    assert ipc_server._ws_clients == set()
    assert "ping" in ipc_server._handlers
    assert "providers.list" in ipc_server._handlers


def test_get_url(ipc_server):
    """Test get_url method."""
    url = ipc_server.get_url()
    assert url == "ws://127.0.0.1:8765/ws"


def test_handle_ping(ipc_server):
    """Test ping handler (run sync)."""
    result = asyncio.run(ipc_server._handle_ping({}))
    assert result["pong"] is True
    assert "timestamp" in result


def test_handle_providers_list(ipc_server):
    """Test providers.list handler (run sync)."""
    with patch("app.ipc.manager") as mock_manager:
        mock_provider = MagicMock()
        mock_provider.model_dump.return_value = {"id": "test", "type": "openrouter"}
        mock_manager.list_providers.return_value = [mock_provider]

        result = asyncio.run(ipc_server._handle_providers_list({}))
        assert len(result) == 1
        assert result[0]["id"] == "test"


def test_handle_diagnostics(ipc_server):
    """Test diagnostics handler (run sync)."""
    with patch("app.ipc.run_all_diagnostics") as mock_diagnostics:
        mock_result = MagicMock()
        mock_result.name = "Test"
        mock_result.status = "ok"
        mock_result.details = "Details"
        mock_result.remediation = None
        mock_diagnostics.return_value = [mock_result]

        result = asyncio.run(ipc_server._handle_diagnostics({}))
        assert len(result) == 1
        assert result[0]["name"] == "Test"
        assert result[0]["status"] == "ok"


def test_handle_settings_get(ipc_server):
    """Test settings.get handler (run sync)."""
    with patch("app.ipc.settings") as mock_settings:
        mock_settings.server.model_dump.return_value = {"host": "127.0.0.1", "port": 8765}
        mock_settings.security.model_dump.return_value = {"allowed_origins": []}
        mock_settings.ui.model_dump.return_value = {"theme": "dark"}
        mock_settings.ai.model_dump.return_value = {"default_provider": "openrouter"}

        result = asyncio.run(ipc_server._handle_settings_get({}))
        assert "server" in result
        assert "security" in result
        assert "ui" in result
        assert "ai" in result


def test_handle_shutdown(ipc_server):
    """Test shutdown handler (run sync)."""
    result = asyncio.run(ipc_server._handle_shutdown({}))
    assert result["shutting_down"] is True
    assert ipc_server.shutdown_requested is True