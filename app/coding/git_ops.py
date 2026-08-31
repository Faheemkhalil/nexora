"""Git operations backend — status, diff, commit, log, branch management."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from loguru import logger

from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


async def _run_git(args: list[str], cwd: str | None = None, timeout: float = 30) -> tuple[str, str, int]:
    """Run a git command asynchronously and return (stdout, stderr, returncode)."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return "", "Command timed out", 1

    return stdout.decode(errors="replace"), stderr.decode(errors="replace"), proc.returncode or 0


class GitStatusTool(BaseTool):
    """Get git status of a repository."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.git.status",
            description="Get git repository status (staged, modified, untracked files).",
            category="coding",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository root path"},
                },
                "required": ["path"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = inputs["path"]
        stdout, stderr, code = await _run_git(["status", "--porcelain"], cwd=path)

        if code != 0:
            return ToolResult(success=False, error=f"git status failed: {stderr.strip()}")

        files = []
        for line in stdout.strip().splitlines():
            if len(line) >= 3:
                index_status = line[0]
                work_status = line[1]
                filepath = line[3:]
                files.append({
                    "path": filepath,
                    "index_status": index_status,
                    "work_status": work_status,
                    "staged": index_status != " ",
                    "modified": work_status != " ",
                })

        # Get branch
        branch_out, _, _ = await _run_git(["branch", "--show-current"], cwd=path)
        branch = branch_out.strip() or "detached"

        self.log_action("git_status", path)
        return ToolResult(
            success=True,
            data={"files": files, "branch": branch, "clean": len(files) == 0},
        )


class GitDiffTool(BaseTool):
    """Show git diff for staged or unstaged changes."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.git.diff",
            description="Show git diff (unstaged by default, or staged with --staged).",
            category="coding",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=15.0,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository root path"},
                    "staged": {"type": "boolean", "description": "Show staged changes"},
                    "file": {"type": "string", "description": "Specific file to diff"},
                },
                "required": ["path"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = inputs["path"]
        args = ["diff"]
        if inputs.get("staged"):
            args.append("--staged")
        if inputs.get("file"):
            args.append("--")
            args.append(inputs["file"])

        stdout, stderr, code = await _run_git(args, cwd=path)
        if code != 0:
            return ToolResult(success=False, error=f"git diff failed: {stderr.strip()}")

        self.log_action("git_diff", path)
        return ToolResult(
            success=True,
            data={"diff": stdout, "empty": len(stdout.strip()) == 0},
        )


class GitLogTool(BaseTool):
    """Show git log."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.git.log",
            description="Show recent git commit log.",
            category="coding",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository root path"},
                    "count": {"type": "integer", "description": "Number of commits to show"},
                },
                "required": ["path"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = inputs["path"]
        count = inputs.get("count", 20)
        stdout, stderr, code = await _run_git(
            ["log", f"-{count}", "--pretty=format:%H|%h|%s|%an|%ai"],
            cwd=path,
        )
        if code != 0:
            return ToolResult(success=False, error=f"git log failed: {stderr.strip()}")

        commits = []
        for line in stdout.strip().splitlines():
            parts = line.split("|", 4)
            if len(parts) >= 5:
                commits.append({
                    "hash": parts[0],
                    "short_hash": parts[1],
                    "message": parts[2],
                    "author": parts[3],
                    "date": parts[4],
                })

        self.log_action("git_log", path, details=f"commits={len(commits)}")
        return ToolResult(success=True, data={"commits": commits})


class GitAddTool(BaseTool):
    """Stage files for commit."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.git.add",
            description="Stage files for commit.",
            category="coding",
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository root path"},
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to stage (or ['*'] for all)",
                    },
                },
                "required": ["path", "files"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        if not inputs.get("files"):
            return "files list is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = inputs["path"]
        files = inputs["files"]

        args = ["add"] + files
        stdout, stderr, code = await _run_git(args, cwd=path)
        if code != 0:
            return ToolResult(success=False, error=f"git add failed: {stderr.strip()}")

        self.log_action("git_add", path, details=f"files={files}")
        return ToolResult(success=True, data={"staged": files})


class GitCommitTool(BaseTool):
    """Create a git commit."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.git.commit",
            description="Create a git commit with a message.",
            category="coding",
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            timeout=15.0,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository root path"},
                    "message": {"type": "string", "description": "Commit message"},
                    "author_name": {"type": "string", "description": "Author name"},
                    "author_email": {"type": "string", "description": "Author email"},
                },
                "required": ["path", "message"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        if not inputs.get("message"):
            return "commit message is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = inputs["path"]
        message = inputs["message"]
        env = os.environ.copy()

        if inputs.get("author_name"):
            env["GIT_AUTHOR_NAME"] = inputs["author_name"]
        if inputs.get("author_email"):
            env["GIT_AUTHOR_EMAIL"] = inputs["author_email"]

        proc = await asyncio.create_subprocess_exec(
            "git", "commit", "-m", message,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=path,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        stdout_str = stdout.decode(errors="replace")
        stderr_str = stderr.decode(errors="replace")

        if proc.returncode != 0:
            return ToolResult(success=False, error=f"git commit failed: {stderr_str.strip()}")

        # Extract commit hash
        hash_line = stdout_str.strip().splitlines()[0] if stdout_str.strip() else ""
        commit_hash = hash_line.split()[-1] if "[" in hash_line else ""

        self.log_action("git_commit", path, details=f"message={message[:60]}")
        return ToolResult(
            success=True,
            data={"commit_hash": commit_hash, "message": message, "output": stdout_str.strip()},
        )


class GitBranchTool(BaseTool):
    """List branches or create/switch branches."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.git.branch",
            description="List branches, create a new branch, or switch branches.",
            category="coding",
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository root path"},
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "checkout", "delete"],
                        "description": "Branch operation",
                    },
                    "name": {"type": "string", "description": "Branch name (for create/checkout/delete)"},
                },
                "required": ["path", "action"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        action = inputs.get("action")
        if action not in ("list", "create", "checkout", "delete"):
            return f"Invalid action: {action}"
        if action in ("create", "checkout", "delete") and not inputs.get("name"):
            return "branch name is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = inputs["path"]
        action = inputs["action"]
        name = inputs.get("name", "")

        if action == "list":
            stdout, stderr, code = await _run_git(["branch", "-a", "--format=%(refname:short)|%(HEAD)"], cwd=path)
            if code != 0:
                return ToolResult(success=False, error=stderr.strip())

            branches = []
            current = ""
            for line in stdout.strip().splitlines():
                parts = line.split("|", 1)
                bname = parts[0].strip()
                is_current = parts[1].strip() == "*" if len(parts) > 1 else False
                if is_current:
                    current = bname
                branches.append({"name": bname, "current": is_current})

            return ToolResult(success=True, data={"branches": branches, "current": current})

        elif action == "create":
            stdout, stderr, code = await _run_git(["checkout", "-b", name], cwd=path)
            if code != 0:
                return ToolResult(success=False, error=stderr.strip())
            return ToolResult(success=True, data={"created": name})

        elif action == "checkout":
            stdout, stderr, code = await _run_git(["checkout", name], cwd=path)
            if code != 0:
                return ToolResult(success=False, error=stderr.strip())
            return ToolResult(success=True, data={"checked_out": name})

        elif action == "delete":
            stdout, stderr, code = await _run_git(["branch", "-d", name], cwd=path)
            if code != 0:
                return ToolResult(success=False, error=stderr.strip())
            return ToolResult(success=True, data={"deleted": name})

        return ToolResult(success=False, error="Unknown action")


def register_git_tools(registry: Any) -> None:
    """Register all git tools."""
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    registry.register(GitLogTool())
    registry.register(GitAddTool())
    registry.register(GitCommitTool())
    registry.register(GitBranchTool())
