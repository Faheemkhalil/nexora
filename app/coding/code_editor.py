"""Code editor backend — file read/write, search, and metadata operations."""

from __future__ import annotations

import fnmatch
import os
import time
from pathlib import Path
from typing import Any

from loguru import logger

from ..core.errors import ToolError
from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


class ReadFileTool(BaseTool):
    """Read a file's content."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.read_file",
            description="Read the content of a file.",
            category="coding",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                    "offset": {"type": "integer", "description": "Start line (0-based)"},
                    "limit": {"type": "integer", "description": "Max lines to read"},
                },
                "required": ["path"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        p = inputs.get("path", "")
        if not p:
            return "path is required"
        if not os.path.isfile(p):
            return f"File not found: {p}"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = inputs["path"]
        offset = inputs.get("offset", 0)
        limit = inputs.get("limit", 2000)

        try:
            with open(path, "r", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            selected = lines[offset : offset + limit]

            self.log_action("read", path)
            return ToolResult(
                success=True,
                data={
                    "content": "".join(selected),
                    "total_lines": total_lines,
                    "offset": offset,
                    "lines_read": len(selected),
                    "truncated": (offset + limit) < total_lines,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WriteFileTool(BaseTool):
    """Write content to a file."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.write_file",
            description="Write content to a file (creates or overwrites).",
            category="coding",
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                    "create_dirs": {"type": "boolean", "description": "Create parent directories if missing"},
                },
                "required": ["path", "content"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        if "content" not in inputs:
            return "content is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = inputs["path"]
        content = inputs["content"]
        create_dirs = inputs.get("create_dirs", False)

        try:
            p = Path(path)
            if create_dirs:
                p.parent.mkdir(parents=True, exist_ok=True)

            # Backup existing file
            existed = p.exists()
            backup = None
            if existed:
                backup_path = p.with_suffix(p.suffix + ".nexora_backup")
                backup = str(backup_path)
                import shutil
                shutil.copy2(path, backup)

            with open(path, "w") as f:
                f.write(content)

            self.log_action("write", path, details=f"backup={backup}")
            return ToolResult(
                success=True,
                data={"path": path, "bytes_written": len(content.encode()), "existed": existed},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SearchFilesTool(BaseTool):
    """Search for text patterns across files in a directory."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.search",
            description="Search for text patterns in files (like ripgrep).",
            category="coding",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=30.0,
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern (regex)"},
                    "path": {"type": "string", "description": "Directory to search in"},
                    "glob": {"type": "string", "description": "File glob pattern (e.g. '*.ts')"},
                    "max_results": {"type": "integer", "description": "Max results to return"},
                    "case_insensitive": {"type": "boolean", "description": "Case-insensitive search"},
                },
                "required": ["pattern"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("pattern"):
            return "pattern is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import re

        pattern = inputs["pattern"]
        search_path = inputs.get("path", ".")
        glob_pattern = inputs.get("glob")
        max_results = inputs.get("max_results", 200)
        case_insensitive = inputs.get("case_insensitive", False)

        try:
            flags = re.IGNORECASE if case_insensitive else 0
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(success=False, error=f"Invalid regex: {e}")

        results: list[dict[str, Any]] = []
        files_searched = 0

        try:
            for root, dirs, files in os.walk(search_path):
                # Skip hidden and common non-source directories
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"node_modules", "__pycache__", "venv", "env", "dist", "build"}]

                for fname in files:
                    if glob_pattern and not fnmatch.fnmatch(fname, glob_pattern):
                        continue
                    if fname.endswith((".pyc", ".pyo", ".so", ".o", ".bin", ".exe", ".png", ".jpg", ".gif")):
                        continue

                    fpath = os.path.join(root, fname)
                    files_searched += 1

                    try:
                        with open(fpath, "r", errors="replace") as f:
                            for i, line in enumerate(f, 1):
                                if regex.search(line):
                                    results.append({
                                        "file": fpath,
                                        "line": i,
                                        "content": line.rstrip()[:200],
                                    })
                                    if len(results) >= max_results:
                                        break
                    except (PermissionError, OSError):
                        continue

                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break

            self.log_action("search", search_path, details=f"pattern={pattern} results={len(results)}")
            return ToolResult(
                success=True,
                data={
                    "results": results,
                    "total_matches": len(results),
                    "files_searched": files_searched,
                    "truncated": len(results) >= max_results,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ListDirTool(BaseTool):
    """List directory contents with metadata."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.list_dir",
            description="List directory contents with file metadata.",
            category="coding",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                    "show_hidden": {"type": "boolean", "description": "Include hidden files"},
                    "recursive": {"type": "boolean", "description": "List recursively (limited depth)"},
                },
                "required": ["path"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        p = inputs.get("path", "")
        if not p:
            return "path is required"
        if not os.path.isdir(p):
            return f"Not a directory: {p}"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = inputs["path"]
        show_hidden = inputs.get("show_hidden", False)

        try:
            entries = []
            for name in sorted(os.listdir(path)):
                if not show_hidden and name.startswith("."):
                    continue
                full = os.path.join(path, name)
                try:
                    stat = os.stat(full)
                    entries.append({
                        "name": name,
                        "type": "dir" if os.path.isdir(full) else "file",
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "path": full,
                    })
                except OSError:
                    continue

            self.log_action("list_dir", path, details=f"entries={len(entries)}")
            return ToolResult(
                success=True,
                data={"path": path, "entries": entries, "count": len(entries)},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


def register_code_tools(registry: Any) -> None:
    """Register all coding tools."""
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(SearchFilesTool())
    registry.register(ListDirTool())
