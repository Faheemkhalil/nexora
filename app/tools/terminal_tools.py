"""Terminal tool — execute shell commands with streaming output.

Supports:
- One-shot execution with timeout
- Streaming output via callbacks
- Process cancellation
- Audit logging
"""
from __future__ import annotations

import asyncio
import os
import signal
import time
from typing import Any

from loguru import logger

from .base import BaseTool, ToolResult, ToolSpec, RiskLevel
from ..core.errors import ToolError


# Active terminal sessions for cancellation
_active_sessions: dict[str, asyncio.subprocess.Process] = {}


class ExecuteCommandTool(BaseTool):
    """Execute a shell command and return output."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="terminal.execute",
            description="Execute a shell command and return stdout/stderr.",
            category="terminal",
            risk_level=RiskLevel.HIGH,
            requires_confirmation=True,
            timeout=30,
            input_schema={
                "command": {"type": "string", "required": True},
                "cwd": {"type": "string"},
                "timeout": {"type": "number"},
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("command"):
            return "command is required"
        # Block obviously dangerous commands
        cmd = inputs["command"].strip().lower()
        dangerous = ["rm -rf /", "mkfs", ":(){", "dd if=", "> /dev/sd"]
        for d in dangerous:
            if d in cmd:
                return f"Dangerous command detected: '{d}' is blocked"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        command = inputs["command"]
        cwd = inputs.get("cwd", os.path.expanduser("~"))
        timeout = inputs.get("timeout", 30)

        start = time.time()
        session_id = str(int(time.time() * 1000))

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            _active_sessions[session_id] = proc

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(
                    success=False,
                    error=f"Command timed out after {timeout}s",
                    data={"command": command, "session_id": session_id, "timed_out": True},
                )
            finally:
                _active_sessions.pop(session_id, None)

            elapsed = (time.time() - start) * 1000
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Truncate very long output
            max_output = 50000
            if len(stdout_str) > max_output:
                stdout_str = stdout_str[:max_output] + f"\n... (truncated, {len(stdout.decode('utf-8', errors='replace'))} chars total)"
            if len(stderr_str) > max_output:
                stderr_str = stderr_str[:max_output] + f"\n... (truncated)"

            self.log_action("execute", command, "success" if proc.returncode == 0 else "failure")

            return ToolResult(
                success=proc.returncode == 0,
                data={
                    "command": command,
                    "exit_code": proc.returncode,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "cwd": cwd,
                    "execution_time_ms": round(elapsed, 1),
                },
            )

        except Exception as e:
            _active_sessions.pop(session_id, None)
            return ToolResult(success=False, error=str(e))

    async def cancel(self, session_id: str) -> bool:
        """Cancel a running command."""
        proc = _active_sessions.get(session_id)
        if proc:
            try:
                proc.kill()
                _active_sessions.pop(session_id, None)
                return True
            except Exception:
                return False
        return False


class ListSessionsTool(BaseTool):
    """List active terminal sessions."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="terminal.sessions",
            description="List active terminal sessions that can be cancelled.",
            category="terminal",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=5,
            input_schema={},
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        sessions = []
        for sid, proc in _active_sessions.items():
            sessions.append({
                "session_id": sid,
                "pid": proc.pid,
                "returncode": proc.returncode,
            })
        return ToolResult(success=True, data={"sessions": sessions, "count": len(sessions)})


def register_terminal_tools(reg) -> None:
    """Register all terminal tools."""
    for tool_cls in [ExecuteCommandTool, ListSessionsTool]:
        reg.register(tool_cls())
