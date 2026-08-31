"""Tests for coding module — code editor, git ops, test runner, AI agent, project manager."""

import asyncio
import os
import tempfile
import time

import pytest


# ============================================================
# Code Editor Tools
# ============================================================

class TestReadFileTool:
    def test_spec(self):
        from app.coding.code_editor import ReadFileTool
        tool = ReadFileTool()
        spec = tool.spec()
        assert spec.name == "coding.read_file"
        assert spec.category == "coding"

    def test_validate_empty_path(self):
        from app.coding.code_editor import ReadFileTool
        tool = ReadFileTool()
        error = asyncio.run(
            tool.validate_inputs({"path": ""})
        )
        assert error is not None

    def test_validate_nonexistent(self):
        from app.coding.code_editor import ReadFileTool
        tool = ReadFileTool()
        error = asyncio.run(
            tool.validate_inputs({"path": "/nonexistent/file.txt"})
        )
        assert error is not None

    def test_read_file(self):
        from app.coding.code_editor import ReadFileTool
        tool = ReadFileTool()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("print('hello')\nprint('world')")
            path = f.name
        try:
            result = asyncio.run(
                tool.execute({"path": path})
            )
            assert result.success
            assert "print('hello')" in result.data["content"]
            assert result.data["total_lines"] == 2
        finally:
            os.unlink(path)

    def test_read_with_offset_limit(self):
        from app.coding.code_editor import ReadFileTool
        tool = ReadFileTool()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("line1\nline2\nline3\nline4\nline5")
            path = f.name
        try:
            result = asyncio.run(
                tool.execute({"path": path, "offset": 1, "limit": 2})
            )
            assert result.success
            assert "line2" in result.data["content"]
            assert "line1" not in result.data["content"]
            assert result.data["lines_read"] == 2
        finally:
            os.unlink(path)


class TestWriteFileTool:
    def test_spec(self):
        from app.coding.code_editor import WriteFileTool
        tool = WriteFileTool()
        spec = tool.spec()
        assert spec.name == "coding.write_file"
        assert spec.risk_level.value == "medium"

    def test_validate_empty_path(self):
        from app.coding.code_editor import WriteFileTool
        tool = WriteFileTool()
        error = asyncio.run(
            tool.validate_inputs({"path": ""})
        )
        assert error is not None

    def test_write_file(self):
        from app.coding.code_editor import WriteFileTool
        tool = WriteFileTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.py")
            result = asyncio.run(
                tool.execute({"path": path, "content": "hello world"})
            )
            assert result.success
            assert result.data["bytes_written"] == 11
            with open(path) as f:
                assert f.read() == "hello world"

    def test_write_with_create_dirs(self):
        from app.coding.code_editor import WriteFileTool
        tool = WriteFileTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "dir", "test.py")
            result = asyncio.run(
                tool.execute({"path": path, "content": "test", "create_dirs": True})
            )
            assert result.success
            assert os.path.isfile(path)


class TestSearchFilesTool:
    def test_spec(self):
        from app.coding.code_editor import SearchFilesTool
        tool = SearchFilesTool()
        assert tool.spec().name == "coding.search"

    def test_search(self):
        from app.coding.code_editor import SearchFilesTool
        tool = SearchFilesTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            with open(os.path.join(tmpdir, "a.py"), 'w') as f:
                f.write("def hello():\n    pass")
            with open(os.path.join(tmpdir, "b.py"), 'w') as f:
                f.write("def world():\n    pass")

            result = asyncio.run(
                tool.execute({"pattern": "def hello", "path": tmpdir})
            )
            assert result.success
            assert result.data["total_matches"] >= 1
            assert any("hello" in r["content"] for r in result.data["results"])

    def test_search_with_glob(self):
        from app.coding.code_editor import SearchFilesTool
        tool = SearchFilesTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "a.py"), 'w') as f:
                f.write("test")
            with open(os.path.join(tmpdir, "b.txt"), 'w') as f:
                f.write("test")

            result = asyncio.run(
                tool.execute({"pattern": "test", "path": tmpdir, "glob": "*.py"})
            )
            assert result.success
            assert all(r["file"].endswith(".py") for r in result.data["results"])


class TestListDirTool:
    def test_spec(self):
        from app.coding.code_editor import ListDirTool
        tool = ListDirTool()
        assert tool.spec().name == "coding.list_dir"

    def test_list_dir(self):
        from app.coding.code_editor import ListDirTool
        tool = ListDirTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "file.txt"), 'w') as f:
                f.write("hello")
            os.mkdir(os.path.join(tmpdir, "subdir"))

            result = asyncio.run(
                tool.execute({"path": tmpdir})
            )
            assert result.success
            names = [e["name"] for e in result.data["entries"]]
            assert "file.txt" in names
            assert "subdir" in names


# ============================================================
# Git Operations
# ============================================================

class TestGitStatusTool:
    def test_spec(self):
        from app.coding.git_ops import GitStatusTool
        tool = GitStatusTool()
        assert tool.spec().name == "coding.git.status"

    def test_validate_empty_path(self):
        from app.coding.git_ops import GitStatusTool
        tool = GitStatusTool()
        error = asyncio.run(
            tool.validate_inputs({"path": ""})
        )
        assert error is not None


class TestGitDiffTool:
    def test_spec(self):
        from app.coding.git_ops import GitDiffTool
        tool = GitDiffTool()
        assert tool.spec().name == "coding.git.diff"


class TestGitLogTool:
    def test_spec(self):
        from app.coding.git_ops import GitLogTool
        tool = GitLogTool()
        assert tool.spec().name == "coding.git.log"


class TestGitAddTool:
    def test_spec(self):
        from app.coding.git_ops import GitAddTool
        tool = GitAddTool()
        assert tool.spec().name == "coding.git.add"


class TestGitCommitTool:
    def test_spec(self):
        from app.coding.git_ops import GitCommitTool
        tool = GitCommitTool()
        spec = tool.spec()
        assert spec.name == "coding.git.commit"
        assert spec.requires_confirmation is True


class TestGitBranchTool:
    def test_spec(self):
        from app.coding.git_ops import GitBranchTool
        tool = GitBranchTool()
        assert tool.spec().name == "coding.git.branch"

    def test_validate_invalid_action(self):
        from app.coding.git_ops import GitBranchTool
        tool = GitBranchTool()
        error = asyncio.run(
            tool.validate_inputs({"path": "/tmp", "action": "invalid"})
        )
        assert error is not None


# ============================================================
# Test Runner
# ============================================================

class TestRunTestsTool:
    def test_spec(self):
        from app.coding.test_runner import RunTestsTool
        tool = RunTestsTool()
        assert tool.spec().name == "coding.test.run"

    def test_detect_framework(self):
        from app.coding.test_runner import RunTestsTool
        tool = RunTestsTool()
        detected = tool._detect_framework("/home/faheemkhalil/NEXORA")
        assert detected in ("pytest", "npm")

    def test_parse_pytest_output(self):
        from app.coding.test_runner import RunTestsTool
        tool = RunTestsTool()
        result = tool._parse_results(
            "pytest",
            "5 passed, 2 failed, 1 skipped in 1.23s",
            "",
            1,
        )
        assert result["passed"] == 5
        assert result["failed"] == 2
        assert result["skipped"] == 1


# ============================================================
# AI Coding Agent
# ============================================================

class TestExplainCodeTool:
    def test_spec(self):
        from app.coding.ai_agent import ExplainCodeTool
        tool = ExplainCodeTool()
        assert tool.spec().name == "coding.agent.explain"

    def test_validate_empty_code(self):
        from app.coding.ai_agent import ExplainCodeTool
        tool = ExplainCodeTool()
        error = asyncio.run(
            tool.validate_inputs({"code": ""})
        )
        assert error is not None


class TestGenerateCodeTool:
    def test_spec(self):
        from app.coding.ai_agent import GenerateCodeTool
        tool = GenerateCodeTool()
        assert tool.spec().name == "coding.agent.generate"


class TestFindBugsTool:
    def test_spec(self):
        from app.coding.ai_agent import FindBugsTool
        tool = FindBugsTool()
        assert tool.spec().name == "coding.agent.find_bugs"


class TestCreateTestsTool:
    def test_spec(self):
        from app.coding.ai_agent import CreateTestsTool
        tool = CreateTestsTool()
        assert tool.spec().name == "coding.agent.create_tests"


# ============================================================
# Project Manager
# ============================================================

class TestProjectListTool:
    def test_spec(self):
        from app.coding.project_manager import ProjectListTool
        tool = ProjectListTool()
        assert tool.spec().name == "coding.projects.list"


class TestProjectOpenTool:
    def test_spec(self):
        from app.coding.project_manager import ProjectOpenTool
        tool = ProjectOpenTool()
        assert tool.spec().name == "coding.projects.open"

    def test_validate_empty_path(self):
        from app.coding.project_manager import ProjectOpenTool
        tool = ProjectOpenTool()
        error = asyncio.run(
            tool.validate_inputs({"path": ""})
        )
        assert error is not None

    def test_open_project(self):
        from app.coding.project_manager import ProjectOpenTool
        from app.core.db import init_db
        asyncio.run(init_db())
        tool = ProjectOpenTool()
        result = asyncio.run(
            tool.execute({"path": "/home/faheemkhalil/NEXORA"})
        )
        assert result.success
        assert result.data["name"] == "NEXORA"
        assert result.data["type"] == "python"
        assert result.data["is_git"] is True


# ============================================================
# Registry Integration
# ============================================================

class TestCodingRegistry:
    def test_register_all(self):
        from app.tools.registry import ToolRegistry
        reg = ToolRegistry()
        from app.coding.code_editor import register_code_tools
        from app.coding.git_ops import register_git_tools
        from app.coding.test_runner import register_test_tools
        from app.coding.ai_agent import register_ai_tools
        from app.coding.project_manager import register_project_tools

        register_code_tools(reg)
        register_git_tools(reg)
        register_test_tools(reg)
        register_ai_tools(reg)
        register_project_tools(reg)

        tools = reg.list_tools()
        names = {t.name for t in tools}
        assert "coding.read_file" in names
        assert "coding.write_file" in names
        assert "coding.search" in names
        assert "coding.list_dir" in names
        assert "coding.git.status" in names
        assert "coding.git.diff" in names
        assert "coding.git.log" in names
        assert "coding.git.add" in names
        assert "coding.git.commit" in names
        assert "coding.git.branch" in names
        assert "coding.test.run" in names
        assert "coding.agent.explain" in names
        assert "coding.agent.generate" in names
        assert "coding.agent.refactor" in names
        assert "coding.agent.find_bugs" in names
        assert "coding.agent.create_tests" in names
        assert "coding.projects.list" in names
        assert "coding.projects.open" in names

        assert len(tools) == 18

    def test_coding_category(self):
        from app.tools.registry import ToolRegistry
        reg = ToolRegistry()
        from app.coding.code_editor import register_code_tools
        from app.coding.git_ops import register_git_tools
        from app.coding.test_runner import register_test_tools
        from app.coding.ai_agent import register_ai_tools
        from app.coding.project_manager import register_project_tools

        register_code_tools(reg)
        register_git_tools(reg)
        register_test_tools(reg)
        register_ai_tools(reg)
        register_project_tools(reg)

        coding_tools = reg.list_tools(category="coding")
        assert len(coding_tools) == 18
