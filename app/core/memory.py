"""Memory system — scoped memory storage for global, project, and conversation contexts."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from loguru import logger

from .db import execute as db_execute
from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


class MemoryStore:
    """In-memory cache backed by SQLite for persistent memory."""

    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}

    async def set(
        self,
        scope: str,
        key: str,
        value: str,
        ttl: float | None = None,
    ) -> str:
        """Store a memory entry."""
        memory_id = str(uuid.uuid4())[:12]
        now = time.time()
        expires_at = now + ttl if ttl else None

        await db_execute(
            """INSERT OR REPLACE INTO memory (id, scope, key, value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (memory_id, scope, key, value, now, now),
        )

        self._cache[f"{scope}:{key}"] = {
            "id": memory_id,
            "scope": scope,
            "key": key,
            "value": value,
            "created_at": now,
            "updated_at": now,
        }

        logger.debug(f"Memory stored: [{scope}] {key}")
        return memory_id

    async def get(self, scope: str, key: str) -> dict | None:
        """Retrieve a memory entry."""
        cache_key = f"{scope}:{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        row = await db_execute(
            "SELECT * FROM memory WHERE scope = ? AND key = ?",
            (scope, key),
            fetch="one",
        )
        if row:
            entry = dict(row)
            self._cache[cache_key] = entry
            return entry
        return None

    async def search(self, scope: str | None = None, query: str = "", limit: int = 50) -> list[dict]:
        """Search memory entries."""
        if query:
            # Use LIKE for text search
            if scope:
                rows = await db_execute(
                    "SELECT * FROM memory WHERE scope = ? AND (key LIKE ? OR value LIKE ?) ORDER BY updated_at DESC LIMIT ?",
                    (scope, f"%{query}%", f"%{query}%", limit),
                    fetch="all",
                )
            else:
                rows = await db_execute(
                    "SELECT * FROM memory WHERE key LIKE ? OR value LIKE ? ORDER BY updated_at DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit),
                    fetch="all",
                )
        elif scope:
            rows = await db_execute(
                "SELECT * FROM memory WHERE scope = ? ORDER BY updated_at DESC LIMIT ?",
                (scope, limit),
                fetch="all",
            )
        else:
            rows = await db_execute(
                "SELECT * FROM memory ORDER BY updated_at DESC LIMIT ?",
                (limit,),
                fetch="all",
            )

        return [dict(r) for r in (rows or [])]

    async def delete(self, scope: str, key: str) -> bool:
        """Delete a memory entry."""
        cache_key = f"{scope}:{key}"
        self._cache.pop(cache_key, None)

        await db_execute(
            "DELETE FROM memory WHERE scope = ? AND key = ?",
            (scope, key),
        )
        logger.debug(f"Memory deleted: [{scope}] {key}")
        return True

    async def clear(self, scope: str | None = None) -> int:
        """Clear memory entries. Returns count deleted."""
        if scope:
            rows = await db_execute(
                "SELECT id FROM memory WHERE scope = ?", (scope,), fetch="all"
            )
            count = len(rows) if rows else 0
            await db_execute("DELETE FROM memory WHERE scope = ?", (scope,))
        else:
            rows = await db_execute("SELECT id FROM memory", fetch="all")
            count = len(rows) if rows else 0
            await db_execute("DELETE FROM memory")
            self._cache.clear()

        logger.info(f"Memory cleared: {count} entries")
        return count

    async def list_scopes(self) -> list[dict]:
        """List all scopes with their entry counts."""
        rows = await db_execute(
            "SELECT scope, COUNT(*) as count FROM memory GROUP BY scope",
            fetch="all",
        )
        return [{"scope": r["scope"], "count": r["count"]} for r in (rows or [])]


# Global instance
memory = MemoryStore()


# ============================================================
# Tool Wrappers
# ============================================================

class MemorySetTool(BaseTool):
    """Store a memory entry."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="memory.set",
            description="Store a memory entry with a key and value.",
            category="memory",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=5.0,
            input_schema={
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["global", "project", "conversation"], "description": "Memory scope"},
                    "key": {"type": "string", "description": "Memory key"},
                    "value": {"type": "string", "description": "Memory value"},
                    "ttl": {"type": "number", "description": "Time-to-live in seconds (null for permanent)"},
                },
                "required": ["scope", "key", "value"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        for field in ("scope", "key", "value"):
            if not inputs.get(field):
                return f"{field} is required"
        if inputs["scope"] not in ("global", "project", "conversation"):
            return f"Invalid scope: {inputs['scope']}"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        memory_id = await memory.set(
            scope=inputs["scope"],
            key=inputs["key"],
            value=inputs["value"],
            ttl=inputs.get("ttl"),
        )
        self.log_action("memory_set", details=f"[{inputs['scope']}] {inputs['key']}")
        return ToolResult(success=True, data={"id": memory_id, "scope": inputs["scope"], "key": inputs["key"]})


class MemoryGetTool(BaseTool):
    """Retrieve a memory entry."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="memory.get",
            description="Retrieve a memory entry by scope and key.",
            category="memory",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=5.0,
            input_schema={
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["global", "project", "conversation"]},
                    "key": {"type": "string"},
                },
                "required": ["scope", "key"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        for field in ("scope", "key"):
            if not inputs.get(field):
                return f"{field} is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        entry = await memory.get(inputs["scope"], inputs["key"])
        if entry:
            return ToolResult(success=True, data=entry)
        return ToolResult(success=False, error=f"Memory not found: [{inputs['scope']}] {inputs['key']}")


class MemorySearchTool(BaseTool):
    """Search memory entries."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="memory.search",
            description="Search memory entries by scope and/or query.",
            category="memory",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "description": "Filter by scope"},
                    "query": {"type": "string", "description": "Search query (matches key and value)"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
            },
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        results = await memory.search(
            scope=inputs.get("scope"),
            query=inputs.get("query", ""),
            limit=inputs.get("limit", 50),
        )
        return ToolResult(success=True, data={"memories": results, "total": len(results)})


class MemoryDeleteTool(BaseTool):
    """Delete a memory entry."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="memory.delete",
            description="Delete a memory entry by scope and key.",
            category="memory",
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            timeout=5.0,
            input_schema={
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["global", "project", "conversation"]},
                    "key": {"type": "string"},
                },
                "required": ["scope", "key"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        for field in ("scope", "key"):
            if not inputs.get(field):
                return f"{field} is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await memory.delete(inputs["scope"], inputs["key"])
        self.log_action("memory_delete", details=f"[{inputs['scope']}] {inputs['key']}")
        return ToolResult(success=True, data={"deleted": True, "scope": inputs["scope"], "key": inputs["key"]})


class MemoryClearTool(BaseTool):
    """Clear all memory in a scope."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="memory.clear",
            description="Clear all memory entries in a scope (or all scopes).",
            category="memory",
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "description": "Scope to clear (omit for all)"},
                },
            },
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        count = await memory.clear(scope=inputs.get("scope"))
        self.log_action("memory_clear", details=f"deleted={count}")
        return ToolResult(success=True, data={"deleted_count": count})


class MemoryScopesTool(BaseTool):
    """List all memory scopes with counts."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="memory.scopes",
            description="List all memory scopes with entry counts.",
            category="memory",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=5.0,
            input_schema={"type": "object", "properties": {}},
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        scopes = await memory.list_scopes()
        return ToolResult(success=True, data={"scopes": scopes})


def register_memory_tools(registry: Any) -> None:
    """Register all memory tools."""
    registry.register(MemorySetTool())
    registry.register(MemoryGetTool())
    registry.register(MemorySearchTool())
    registry.register(MemoryDeleteTool())
    registry.register(MemoryClearTool())
    registry.register(MemoryScopesTool())
