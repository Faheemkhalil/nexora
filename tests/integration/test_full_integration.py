"""Comprehensive integration test — verifies all 8 NEXORA phases work together end-to-end.

Run with: python3 -m pytest tests/integration/test_full_integration.py -v
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time

import pytest

from app.core.db import init_db


# ============================================================
# Phase 1: Foundation
# ============================================================

class TestPhase1Foundation:
    """Tests: Desktop shell, 3D UI, Backend, IPC, Configuration, Logging, SQLite."""

    def test_database_initializes(self):
        asyncio.run(init_db())
        from app.core.db import execute
        rows = asyncio.run(execute("SELECT name FROM sqlite_master WHERE type='table'", fetch="all"))
        table_names = {r["name"] for r in (rows or [])}
        assert "conversations" in table_names
        assert "messages" in table_names
        assert "providers" in table_names
        assert "settings" in table_names

    def test_config_loads(self):
        from app.core.config import settings
        assert settings.server.host == "127.0.0.1"
        assert settings.server.port == 8765
        assert settings.security is not None
        assert settings.ui is not None
        assert settings.ai is not None

    def test_error_types_exist(self):
        from app.core.errors import (
            NexoraError, ConfigurationError, ProviderError,
            AuthenticationError, NetworkError, ToolError,
            PermissionError, ValidationError, VoiceError,
            DatabaseError, SecurityScopeError, UIError,
        )
        # All error types should be importable
        assert issubclass(ConfigurationError, NexoraError)
        assert issubclass(ProviderError, NexoraError)
        assert issubclass(ToolError, NexoraError)

    def test_ipc_server_creation(self):
        from app.ipc import IPCServer
        server = IPCServer()
        url = server.get_url()
        assert "ws://" in url
        assert "8765" in url


# ============================================================
# Phase 2: AI Providers
# ============================================================

class TestPhase2AIProviders:
    """Tests: Provider abstraction, OpenRouter, Custom, Local, Chat, Streaming."""

    def test_provider_manager_exists(self):
        from app.providers import manager
        assert manager is not None

    def test_base_provider_interface(self):
        from app.providers.base import BaseProvider, ChatMessage, ChatResponse
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        resp = ChatResponse(content="hi", provider="test", model="m", streaming=False)
        assert resp.content == "hi"

    def test_provider_config_model(self):
        from app.providers.base import ProviderConfig
        config = ProviderConfig(
            id="test", type="custom", name="Test",
            model="gpt-4", configured=True,
        )
        assert config.id == "test"
        assert config.configured is True

    def test_custom_provider_instantiation(self):
        from app.providers.custom import CustomProvider
        from app.providers.base import ProviderConfig
        config = ProviderConfig(
            id="test-custom", type="custom", name="Test",
            model="gpt-4", configured=True,
            base_url="https://api.example.com",
        )
        provider = CustomProvider(config)
        assert provider.id == "test-custom"
        assert provider.model == "gpt-4"


# ============================================================
# Phase 3: Voice
# ============================================================

class TestPhase3Voice:
    """Tests: STT, TTS, microphone, voice states."""

    def test_voice_states_exist(self):
        from app.voice import VoiceState
        assert VoiceState.IDLE.value == "idle"
        assert VoiceState.LISTENING.value == "listening"
        assert VoiceState.THINKING.value == "thinking"
        assert VoiceState.SPEAKING.value == "speaking"

    def test_stt_factory(self):
        from app.voice.stt import create_stt
        stt = create_stt("google")
        assert stt is not None

    def test_tts_factory(self):
        from app.voice.tts import create_tts
        tts = create_tts("edge")
        assert tts is not None

    def test_voice_manager_init(self):
        from app.voice import VoiceManager, VoiceState
        vm = VoiceManager(stt_engine="google", tts_engine="edge")
        assert vm.state == VoiceState.IDLE
        asyncio.run(vm.close())


# ============================================================
# Phase 4: PC Control
# ============================================================

class TestPhase4PCControl:
    """Tests: File tools, system tools, terminal, permissions."""

    def test_file_read_tool(self):
        from app.tools.file_tools import ReadFileTool
        tool = ReadFileTool()
        assert tool.spec().name == "file.read"

    def test_file_write_tool(self):
        from app.tools.file_tools import WriteFileTool
        tool = WriteFileTool()
        assert tool.spec().name == "file.write"
        assert tool.spec().requires_confirmation is True

    def test_system_info_tool(self):
        from app.tools.system_tools import SystemInfoTool
        tool = SystemInfoTool()
        result = asyncio.run(tool.execute({}))
        assert result.success
        assert "os" in result.data

    def test_terminal_execute_tool(self):
        from app.tools.terminal_tools import ExecuteCommandTool
        tool = ExecuteCommandTool()
        assert tool.spec().name == "terminal.execute"

    def test_permissions_manager(self):
        from app.tools.permissions import permissions
        permissions.emergency_stop()
        assert permissions.is_emergency_stopped
        permissions.reset_emergency_stop()
        assert not permissions.is_emergency_stopped

    def test_tool_registry(self):
        from app.tools.registry import ToolRegistry
        reg = ToolRegistry()
        assert len(reg.list_tools()) == 0
        assert len(reg.list_categories()) == 0


# ============================================================
# Phase 5: Coding
# ============================================================

class TestPhase5Coding:
    """Tests: Code editor, git ops, test runner, AI agent, project manager."""

    def test_code_editor_tools(self):
        from app.coding.code_editor import ReadFileTool, WriteFileTool, SearchFilesTool
        assert ReadFileTool().spec().name == "coding.read_file"
        assert WriteFileTool().spec().name == "coding.write_file"
        assert SearchFilesTool().spec().name == "coding.search"

    def test_git_ops_tools(self):
        from app.coding.git_ops import GitStatusTool, GitLogTool, GitBranchTool
        assert GitStatusTool().spec().name == "coding.git.status"
        assert GitLogTool().spec().name == "coding.git.log"
        assert GitBranchTool().spec().name == "coding.git.branch"

    def test_test_runner(self):
        from app.coding.test_runner import RunTestsTool
        tool = RunTestsTool()
        detected = tool._detect_framework("/home/faheemkhalil/NEXORA")
        assert detected in ("pytest", "npm")

    def test_ai_agent_tools(self):
        from app.coding.ai_agent import ExplainCodeTool, GenerateCodeTool, FindBugsTool
        assert ExplainCodeTool().spec().name == "coding.agent.explain"
        assert GenerateCodeTool().spec().name == "coding.agent.generate"
        assert FindBugsTool().spec().name == "coding.agent.find_bugs"

    def test_project_manager(self):
        asyncio.run(init_db())
        from app.coding.project_manager import ProjectOpenTool
        tool = ProjectOpenTool()
        result = asyncio.run(tool.execute({"path": "/home/faheemkhalil/NEXORA"}))
        assert result.success
        assert result.data["is_git"] is True


# ============================================================
# Phase 6: Internet
# ============================================================

class TestPhase6Internet:
    """Tests: Web search, page fetch, docs, browser."""

    def test_search_tool(self):
        from app.internet.search import WebSearchTool
        tool = WebSearchTool()
        assert tool.spec().name == "internet.search"

    def test_fetch_tool(self):
        from app.internet.fetch import FetchPageTool
        tool = FetchPageTool()
        assert tool.spec().name == "internet.fetch"

    def test_fetch_json_tool(self):
        from app.internet.fetch import FetchJsonTool
        tool = FetchJsonTool()
        assert tool.spec().name == "internet.fetch_json"

    def test_docs_tool(self):
        from app.internet.docs import DocsLookupTool
        tool = DocsLookupTool()
        assert tool.spec().name == "internet.docs"

    def test_browser_tool(self):
        from app.internet.browser import OpenBrowserTool
        tool = OpenBrowserTool()
        assert tool.spec().name == "internet.open"

    def test_live_fetch(self):
        from app.internet.fetch import FetchPageTool
        tool = FetchPageTool()
        result = asyncio.run(tool.execute({"url": "https://example.com", "max_chars": 500}))
        assert result.success
        assert "Example" in result.data.get("title", "") or "example" in result.data.get("content", "").lower()


# ============================================================
# Phase 7: Security
# ============================================================

class TestPhase7Security:
    """Tests: Findings, lab mode, reports, scope management."""

    def test_findings_crud(self):
        asyncio.run(init_db())
        from app.security.findings import CreateFindingTool, ListFindingsTool, FindingsSummaryTool

        # Create
        create = CreateFindingTool()
        result = asyncio.run(create.execute({
            "title": "Integration Test Finding",
            "severity": "medium",
            "affected_asset": "test://integration",
            "description": "Created by integration test",
        }))
        assert result.success
        finding_id = result.data["id"]

        # List
        listing = ListFindingsTool()
        result = asyncio.run(listing.execute({}))
        assert result.success
        assert len(result.data["findings"]) > 0

        # Summary
        summary = FindingsSummaryTool()
        result = asyncio.run(summary.execute({}))
        assert result.success
        assert result.data["total"] > 0

    def test_lab_lifecycle(self):
        asyncio.run(init_db())
        from app.security.lab import LabCreateTool, LabStatusTool, LabStartTool, LabStopTool

        # Create
        create = LabCreateTool()
        result = asyncio.run(create.execute({
            "name": "Integration Test Lab",
            "target": "test://integration",
            "scope": "127.0.0.1",
        }))
        assert result.success
        lab_id = result.data["id"]

        # Status
        status = LabStatusTool()
        result = asyncio.run(status.execute({"lab_id": lab_id}))
        assert result.success
        assert result.data["status"] == "idle"

        # Start
        start = LabStartTool()
        result = asyncio.run(start.execute({"lab_id": lab_id}))
        assert result.success
        assert result.data["status"] == "active"

        # Stop
        stop = LabStopTool()
        result = asyncio.run(stop.execute({"lab_id": lab_id}))
        assert result.success
        assert result.data["status"] == "stopped"

    def test_report_generation(self):
        from app.security.reports import GenerateReportTool
        tool = GenerateReportTool()
        result = asyncio.run(tool.execute({"format": "markdown"}))
        assert result.success
        assert "NEXORA" in result.data["report"]

    def test_report_html(self):
        from app.security.reports import GenerateReportTool
        tool = GenerateReportTool()
        result = asyncio.run(tool.execute({"format": "html"}))
        assert result.success
        assert "<!DOCTYPE html>" in result.data["report"]

    def test_report_pdf(self):
        from app.security.reports import GenerateReportTool
        tool = GenerateReportTool()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            result = asyncio.run(tool.execute({"format": "pdf", "save_path": path}))
            assert result.success
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
            # Verify it's a valid PDF
            with open(path, "rb") as f:
                header = f.read(5)
            assert header == b"%PDF-"
        finally:
            os.unlink(path)

    def test_scope_match(self):
        from app.security.scope import _match_ip, _match_domain, _match_port
        assert _match_ip("192.168.1.1", "192.168.1.0/24")
        assert _match_domain("sub.example.com", "*.example.com")
        assert _match_port(443, "80-444")


# ============================================================
# Phase 8: Advanced
# ============================================================

class TestPhase8Advanced:
    """Tests: Memory system, local AI fallback, diagnostics."""

    def test_memory_lifecycle(self):
        asyncio.run(init_db())
        from app.core.memory import memory

        # Set
        mid = asyncio.run(memory.set("global", "test_key", "test_value"))
        assert mid

        # Get
        entry = asyncio.run(memory.get("global", "test_key"))
        assert entry is not None
        assert entry["value"] == "test_value"

        # Search
        results = asyncio.run(memory.search(query="test"))
        assert len(results) >= 1

        # Delete
        asyncio.run(memory.delete("global", "test_key"))
        entry = asyncio.run(memory.get("global", "test_key"))
        assert entry is None

    def test_memory_scopes(self):
        asyncio.run(init_db())
        from app.core.memory import memory

        asyncio.run(memory.set("global", "g1", "v1"))
        asyncio.run(memory.set("project", "p1", "v2"))
        scopes = asyncio.run(memory.list_scopes())
        assert len(scopes) >= 2

        # Clear project scope
        count = asyncio.run(memory.clear("project"))
        assert count >= 1

    def test_local_ai_detection(self):
        from app.core.local_ai import detect_local_ai
        result = asyncio.run(detect_local_ai())
        # May or may not find a local AI — just verify no crash
        assert result is None or isinstance(result, dict)

    def test_diagnostics(self):
        from app.core.diagnostics import run_all_diagnostics
        results = asyncio.run(run_all_diagnostics())
        assert len(results) >= 8  # At least 8 checks
        for r in results:
            assert r.status in ("ok", "warning", "error")


# ============================================================
# Full IPC Integration
# ============================================================

class TestFullIPC:
    """Test the full IPC server with all registered tools."""

    def test_all_tools_registered(self):
        asyncio.run(init_db())
        from app.ipc import IPCServer

        async def _run():
            server = IPCServer()
            await server.start()

            from app.tools import registry
            tools = registry.list_tools()
            names = {t.name for t in tools}

            # Verify tools from every phase
            assert "file.read" in names           # Phase 4
            assert "system.info" in names         # Phase 4
            assert "coding.read_file" in names    # Phase 5
            assert "coding.git.status" in names   # Phase 5
            assert "internet.search" in names     # Phase 6
            assert "internet.fetch" in names      # Phase 6
            assert "security.findings.create" in names  # Phase 7
            assert "security.lab.create" in names       # Phase 7
            assert "security.reports.generate" in names # Phase 7
            assert "memory.set" in names          # Phase 8

            categories = {t.category for t in tools}
            assert "files" in categories
            assert "system" in categories
            assert "coding" in categories
            assert "internet" in categories
            assert "security" in categories
            assert "memory" in categories

            assert len(tools) >= 55

            await server.stop()

        asyncio.run(_run())

    def test_tool_execution_via_registry(self):
        """Execute tools from different phases through the registry."""
        asyncio.run(init_db())

        async def _run():
            from app.ipc import IPCServer
            server = IPCServer()
            await server.start()

            from app.tools import registry

            # System info (Phase 4)
            result = await registry.execute("system.info", {})
            assert result.success
            assert "os" in result.data

            # Git status (Phase 5)
            result = await registry.execute("coding.git.status", {"path": "/home/faheemkhalil/NEXORA"})
            assert result.success

            # Memory set (Phase 8)
            result = await registry.execute("memory.set", {
                "scope": "global",
                "key": "integration_test",
                "value": "works!",
            })
            assert result.success

            # Memory get (Phase 8)
            result = await registry.execute("memory.get", {
                "scope": "global",
                "key": "integration_test",
            })
            assert result.success
            assert result.data["value"] == "works!"

            # Findings summary (Phase 7)
            result = await registry.execute("security.findings.summary", {})
            assert result.success

            await server.stop()

        asyncio.run(_run())
