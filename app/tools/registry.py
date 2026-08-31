"""Tool registry — central catalog of all available tools.

Tools self-register on import. The registry provides:
- Lookup by name
- List by category
- Execute with permission checks
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from loguru import logger

from .base import BaseTool, ToolResult, ToolSpec, RiskLevel
from ..core.db import execute as db_execute
from ..core.errors import ToolError, PermissionError


class ToolRegistry:
    """Central registry of all NEXORA tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._confirmation_tokens: dict[str, dict] = {}  # token → tool info

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        spec = tool.spec()
        self._tools[spec.name] = tool
        logger.debug(f"Tool registered: {spec.name} (risk={spec.risk_level.value})")

    def get(self, name: str) -> BaseTool:
        """Get a tool by name."""
        if name not in self._tools:
            raise ToolError(f"Tool '{name}' not found.", details=f"Available: {', '.join(self._tools.keys())}")
        return self._tools[name]

    def list_tools(self, category: str | None = None) -> list[ToolSpec]:
        """List all registered tools, optionally filtered by category."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.spec().category == category]
        return [t.spec() for t in tools]

    def list_categories(self) -> list[str]:
        """List all tool categories."""
        categories = set()
        for tool in self._tools.values():
            categories.add(tool.spec().category)
        return sorted(categories)

    async def execute(self, name: str, inputs: dict[str, Any], confirmed: bool = False) -> ToolResult:
        """Execute a tool with permission checking and audit logging.

        If the tool requires confirmation and `confirmed` is False,
        returns a confirmation request instead of executing.
        """
        tool = self.get(name)
        spec = tool.spec()

        # Validate inputs
        validation_error = await tool.validate_inputs(inputs)
        if validation_error:
            return ToolResult(success=False, error=f"Validation failed: {validation_error}")

        # Check if confirmation is needed
        if spec.requires_confirmation and not confirmed:
            token = str(uuid.uuid4())
            self._confirmation_tokens[token] = {
                "tool": name,
                "inputs": inputs,
                "created_at": time.time(),
            }
            return ToolResult(
                success=False,
                error="confirmation_required",
                details=token,
            )

        # Execute
        start = time.time()
        try:
            result = await tool.execute(inputs)
            result.execution_time_ms = (time.time() - start) * 1000

            # Audit log
            outcome = "success" if result.success else "failure"
            await self._audit_log(name, inputs, outcome, result.error or "", result.execution_time_ms)

            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            await self._audit_log(name, inputs, "failure", str(e), elapsed)
            raise ToolError(f"Tool '{name}' failed: {e}")

    async def confirm_and_execute(self, token: str) -> ToolResult:
        """Execute a previously confirmed tool action."""
        if token not in self._confirmation_tokens:
            return ToolResult(success=False, error="Invalid or expired confirmation token.")

        info = self._confirmation_tokens.pop(token)
        return await self.execute(info["tool"], info["inputs"], confirmed=True)

    async def cancel_confirmation(self, token: str) -> None:
        """Cancel a pending confirmation."""
        self._confirmation_tokens.pop(token, None)

    async def _audit_log(self, tool_name: str, inputs: dict, outcome: str, error: str, elapsed_ms: float) -> None:
        """Write an audit log entry."""
        try:
            import json
            await db_execute(
                "INSERT INTO audit_logs (id, action, resource, outcome, details, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    f"tool:{tool_name}",
                    json.dumps(inputs)[:500],
                    outcome,
                    f"elapsed={elapsed_ms:.1f}ms error={error[:200]}" if error else f"elapsed={elapsed_ms:.1f}ms",
                    time.time(),
                ),
            )
        except Exception as e:
            logger.warning(f"Audit log write failed: {e}")


# Global singleton
registry = ToolRegistry()
