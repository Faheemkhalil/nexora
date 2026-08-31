"""File operation tools — read, write, list, search, mkdir, stat."""
from __future__ import annotations

import fnmatch
import os
import time
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult, ToolSpec, RiskLevel
from ..core.errors import ToolError, ValidationError


class ReadFileTool(BaseTool):
    """Read a file's contents."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file.read",
            description="Read the contents of a file.",
            category="files",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10,
            input_schema={"path": {"type": "string", "required": True}, "max_lines": {"type": "integer"}},
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = Path(inputs["path"]).expanduser().resolve()
        if not path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        if not path.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            max_lines = inputs.get("max_lines")
            if max_lines:
                lines = content.split("\n")
                content = "\n".join(lines[:max_lines])
                truncated = len(lines) > max_lines
            else:
                truncated = False

            self.log_action("read", str(path))
            return ToolResult(success=True, data={
                "path": str(path),
                "content": content,
                "size": path.stat().st_size,
                "lines": content.count("\n") + 1,
                "truncated": truncated,
            })
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WriteFileTool(BaseTool):
    """Write content to a file (creates or overwrites)."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file.write",
            description="Write content to a file. Creates parent directories if needed.",
            category="files",
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            timeout=10,
            input_schema={
                "path": {"type": "string", "required": True},
                "content": {"type": "string", "required": True},
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        if "content" not in inputs:
            return "content is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = Path(inputs["path"]).expanduser().resolve()
        content = inputs["content"]

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self.log_action("write", str(path))
            return ToolResult(success=True, data={
                "path": str(path),
                "bytes_written": len(content.encode("utf-8")),
            })
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ListDirectoryTool(BaseTool):
    """List files and directories in a path."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file.list",
            description="List files and directories at a path.",
            category="files",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10,
            input_schema={"path": {"type": "string", "required": True}, "show_hidden": {"type": "boolean"}},
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = Path(inputs["path"]).expanduser().resolve()
        if not path.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")
        if not path.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {path}")

        show_hidden = inputs.get("show_hidden", False)
        entries = []
        try:
            for entry in sorted(path.iterdir()):
                if not show_hidden and entry.name.startswith("."):
                    continue
                stat = entry.stat()
                entries.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": stat.st_size if entry.is_file() else None,
                    "modified": stat.st_mtime,
                    "path": str(entry),
                })

            self.log_action("list", str(path))
            return ToolResult(success=True, data={"path": str(path), "entries": entries, "count": len(entries)})
        except PermissionError as e:
            return ToolResult(success=False, error=f"Permission denied: {e}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SearchFilesTool(BaseTool):
    """Search for files matching a pattern."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file.search",
            description="Search for files matching a glob pattern.",
            category="files",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=30,
            input_schema={
                "path": {"type": "string", "required": True},
                "pattern": {"type": "string", "required": True},
                "max_results": {"type": "integer"},
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        if not inputs.get("pattern"):
            return "pattern is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = Path(inputs["path"]).expanduser().resolve()
        pattern = inputs["pattern"]
        max_results = inputs.get("max_results", 100)

        if not path.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")

        matches = []
        try:
            for root, dirs, files in os.walk(path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    if fnmatch.fnmatch(f, pattern):
                        full = os.path.join(root, f)
                        matches.append(full)
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break

            self.log_action("search", str(path))
            return ToolResult(success=True, data={"matches": matches, "count": len(matches), "pattern": pattern})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class MakeDirTool(BaseTool):
    """Create a directory."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file.mkdir",
            description="Create a directory (and parents).",
            category="files",
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            timeout=5,
            input_schema={"path": {"type": "string", "required": True}},
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = Path(inputs["path"]).expanduser().resolve()
        try:
            path.mkdir(parents=True, exist_ok=True)
            self.log_action("mkdir", str(path))
            return ToolResult(success=True, data={"path": str(path)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class StatFileTool(BaseTool):
    """Get file/directory metadata."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file.stat",
            description="Get file or directory metadata (size, permissions, timestamps).",
            category="files",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=5,
            input_schema={"path": {"type": "string", "required": True}},
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = Path(inputs["path"]).expanduser().resolve()
        if not path.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")

        stat = path.stat()
        import stat as stat_mod
        return ToolResult(success=True, data={
            "path": str(path),
            "type": "dir" if path.is_dir() else "file",
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime,
            "permissions": stat_mod.filemode(stat.st_mode),
        })


# Register all file tools
def register_file_tools(reg) -> None:
    """Register all file tools with the given registry."""
    for tool_cls in [ReadFileTool, WriteFileTool, ListDirectoryTool, SearchFilesTool, MakeDirTool, StatFileTool]:
        reg.register(tool_cls())
