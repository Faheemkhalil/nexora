"""Unit tests for the PC Control tools module."""
import asyncio
import json
import os
import tempfile
import pytest
from pathlib import Path


@pytest.fixture(scope="module")
def loop():
    return asyncio.new_event_loop()


class TestToolRegistry:
    def test_registry_starts_empty(self):
        from app.tools.registry import ToolRegistry
        reg = ToolRegistry()
        assert len(reg.list_tools()) == 0

    def test_register_and_list(self):
        from app.tools.registry import ToolRegistry
        from app.tools.file_tools import ReadFileTool
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        tools = reg.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "file.read"

    def test_get_tool(self):
        from app.tools.registry import ToolRegistry
        from app.tools.file_tools import ReadFileTool
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        assert reg.get("file.read") is not None

    def test_get_unknown_tool_raises(self):
        from app.tools.registry import ToolRegistry
        from app.core.errors import ToolError
        reg = ToolRegistry()
        with pytest.raises(ToolError):
            reg.get("nonexistent.tool")

    def test_list_by_category(self):
        from app.tools.registry import ToolRegistry
        from app.tools.file_tools import ReadFileTool, WriteFileTool
        from app.tools.system_tools import SystemInfoTool
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        reg.register(WriteFileTool())
        reg.register(SystemInfoTool())
        assert len(reg.list_tools("files")) == 2
        assert len(reg.list_tools("system")) == 1

    def test_list_categories(self):
        from app.tools.registry import ToolRegistry
        from app.tools.file_tools import ReadFileTool
        from app.tools.system_tools import SystemInfoTool
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        reg.register(SystemInfoTool())
        cats = reg.list_categories()
        assert "files" in cats
        assert "system" in cats


class TestFileTools:
    def test_read_file(self, loop):
        from app.tools.file_tools import ReadFileTool
        tool = ReadFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world\nline 2")
            path = f.name
        try:
            result = loop.run_until_complete(tool.execute({"path": path}))
            assert result.success is True
            assert "hello world" in result.data["content"]
            assert result.data["lines"] == 2
        finally:
            os.unlink(path)

    def test_read_nonexistent_file(self, loop):
        from app.tools.file_tools import ReadFileTool
        tool = ReadFileTool()
        result = loop.run_until_complete(tool.execute({"path": "/nonexistent/file.txt"}))
        assert result.success is False

    def test_write_file(self, loop):
        from app.tools.file_tools import WriteFileTool
        tool = WriteFileTool()
        path = tempfile.mktemp(suffix=".txt")
        try:
            result = loop.run_until_complete(tool.execute({"path": path, "content": "test content"}))
            assert result.success is True
            assert Path(path).read_text() == "test content"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_list_directory(self, loop):
        from app.tools.file_tools import ListDirectoryTool
        tool = ListDirectoryTool()
        result = loop.run_until_complete(tool.execute({"path": "/tmp"}))
        assert result.success is True
        assert result.data["count"] >= 0

    def test_search_files(self, loop):
        from app.tools.file_tools import SearchFilesTool
        tool = SearchFilesTool()
        result = loop.run_until_complete(tool.execute({"path": "/tmp", "pattern": "*.txt", "max_results": 10}))
        assert result.success is True
        assert "matches" in result.data

    def test_file_stat(self, loop):
        from app.tools.file_tools import StatFileTool
        tool = StatFileTool()
        result = loop.run_until_complete(tool.execute({"path": "/tmp"}))
        assert result.success is True
        assert result.data["type"] == "dir"

    def test_tool_spec_has_risk_level(self):
        from app.tools.file_tools import ReadFileTool, WriteFileTool
        from app.tools.base import RiskLevel
        assert ReadFileTool().spec().risk_level == RiskLevel.SAFE
        assert WriteFileTool().spec().risk_level == RiskLevel.MEDIUM

    def test_write_requires_confirmation(self):
        from app.tools.file_tools import WriteFileTool
        assert WriteFileTool().spec().requires_confirmation is True


class TestSystemTools:
    def test_system_info(self, loop):
        from app.tools.system_tools import SystemInfoTool
        tool = SystemInfoTool()
        result = loop.run_until_complete(tool.execute({}))
        assert result.success is True
        assert "os" in result.data
        assert "cpu" in result.data

    def test_process_list(self, loop):
        from app.tools.system_tools import ProcessListTool
        tool = ProcessListTool()
        result = loop.run_until_complete(tool.execute({"max_results": 5}))
        assert result.success is True
        assert len(result.data["processes"]) <= 5


class TestPermissions:
    def test_emergency_stop(self):
        from app.tools.permissions import PermissionManager
        pm = PermissionManager()
        assert pm.is_emergency_stopped is False
        pm.emergency_stop()
        assert pm.is_emergency_stopped is True
        pm.reset_emergency_stop()
        assert pm.is_emergency_stopped is False

    def test_task_registration(self):
        from app.tools.permissions import PermissionManager
        pm = PermissionManager()
        pm.register_task("t1", "test_task")
        tasks = pm.get_active_tasks()
        assert len(tasks) == 1
        pm.unregister_task("t1")
        assert len(pm.get_active_tasks()) == 0

    def test_cancellation(self):
        from app.tools.permissions import PermissionManager
        pm = PermissionManager()
        pm.register_task("t1", "test_task")
        assert pm.is_cancelled("t1") is False
        pm.emergency_stop()
        assert pm.is_cancelled("t1") is True


class TestToolExecution:
    def test_execute_safe_tool(self, loop):
        from app.tools.registry import ToolRegistry
        from app.tools.system_tools import SystemInfoTool
        reg = ToolRegistry()
        reg.register(SystemInfoTool())
        result = loop.run_until_complete(reg.execute("system.info", {}))
        assert result.success is True

    def test_execute_without_confirmation_returns_token(self, loop):
        from app.tools.registry import ToolRegistry
        from app.tools.file_tools import WriteFileTool
        reg = ToolRegistry()
        reg.register(WriteFileTool())
        result = loop.run_until_complete(
            reg.execute("file.write", {"path": "/tmp/test.txt", "content": "hi"}, confirmed=False)
        )
        assert result.success is False
        assert result.error == "confirmation_required"
        assert result.details is not None

    def test_confirm_and_execute(self, loop):
        from app.tools.registry import ToolRegistry
        from app.tools.file_tools import WriteFileTool
        reg = ToolRegistry()
        reg.register(WriteFileTool())
        path = tempfile.mktemp(suffix=".txt")
        try:
            result = loop.run_until_complete(
                reg.execute("file.write", {"path": path, "content": "confirmed!"}, confirmed=False)
            )
            token = result.details
            result2 = loop.run_until_complete(reg.confirm_and_execute(token))
            assert result2.success is True
            assert Path(path).read_text() == "confirmed!"
        finally:
            if os.path.exists(path):
                os.unlink(path)
