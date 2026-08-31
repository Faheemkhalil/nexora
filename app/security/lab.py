"""Lab mode — manage security assessment labs with target, scope, and status."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from loguru import logger

from ..core.db import execute as db_execute
from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


async def _ensure_table() -> None:
    await db_execute("""
        CREATE TABLE IF NOT EXISTS labs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            target TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'idle',
            config_json TEXT DEFAULT '{}',
            findings_count INTEGER DEFAULT 0,
            started_at REAL,
            stopped_at REAL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)


class LabCreateTool(BaseTool):
    """Create a new security lab assessment."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.lab.create",
            description="Create a new security assessment lab with target and scope.",
            category="security",
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Lab name"},
                    "target": {"type": "string", "description": "Target (IP, domain, URL)"},
                    "scope": {"type": "string", "description": "Scope description (e.g., '192.168.1.0/24, ports 80,443')"},
                    "config": {"type": "object", "description": "Additional configuration"},
                },
                "required": ["name", "target"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("name"):
            return "name is required"
        if not inputs.get("target"):
            return "target is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        lab_id = str(uuid.uuid4())[:8]
        now = time.time()

        await db_execute(
            """INSERT INTO labs (id, name, target, scope, status, config_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lab_id,
                inputs["name"],
                inputs["target"],
                inputs.get("scope", ""),
                "idle",
                json.dumps(inputs.get("config", {})),
                now,
                now,
            ),
        )

        self.log_action("create_lab", inputs["name"], details=f"target={inputs['target']}")
        return ToolResult(
            success=True,
            data={"id": lab_id, "name": inputs["name"], "target": inputs["target"], "status": "idle"},
        )


class LabStatusTool(BaseTool):
    """Get the status of a lab or all labs."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.lab.status",
            description="Get lab status (single lab or all labs).",
            category="security",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "lab_id": {"type": "string", "description": "Specific lab ID (omit for all)"},
                },
            },
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        lab_id = inputs.get("lab_id")

        if lab_id:
            row = await db_execute("SELECT * FROM labs WHERE id = ?", (lab_id,), fetch="one")
            if not row:
                return ToolResult(success=False, error=f"Lab {lab_id} not found")
            return ToolResult(success=True, data=self._row_to_dict(row))

        rows = await db_execute("SELECT * FROM labs ORDER BY created_at DESC", fetch="all")
        labs = [self._row_to_dict(r) for r in (rows or [])]
        return ToolResult(success=True, data={"labs": labs, "total": len(labs)})

    def _row_to_dict(self, row: Any) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "target": row["target"],
            "scope": row["scope"],
            "status": row["status"],
            "config": json.loads(row["config_json"] or "{}"),
            "findings_count": row["findings_count"],
            "started_at": row["started_at"],
            "stopped_at": row["stopped_at"],
            "created_at": row["created_at"],
        }


class LabStartTool(BaseTool):
    """Start a lab assessment."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.lab.start",
            description="Start a security assessment lab.",
            category="security",
            risk_level=RiskLevel.HIGH,
            requires_confirmation=True,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "lab_id": {"type": "string", "description": "Lab ID to start"},
                },
                "required": ["lab_id"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("lab_id"):
            return "lab_id is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        lab_id = inputs["lab_id"]
        row = await db_execute("SELECT * FROM labs WHERE id = ?", (lab_id,), fetch="one")
        if not row:
            return ToolResult(success=False, error=f"Lab {lab_id} not found")

        if row["status"] == "active":
            return ToolResult(success=False, error="Lab is already active")

        now = time.time()
        await db_execute(
            "UPDATE labs SET status = 'active', started_at = ?, updated_at = ? WHERE id = ?",
            (now, now, lab_id),
        )

        self.log_action("start_lab", row["name"], details=f"target={row['target']}")
        return ToolResult(success=True, data={"id": lab_id, "status": "active", "started_at": now})


class LabStopTool(BaseTool):
    """Stop a running lab assessment."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.lab.stop",
            description="Stop a running security assessment lab.",
            category="security",
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "lab_id": {"type": "string", "description": "Lab ID to stop"},
                },
                "required": ["lab_id"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("lab_id"):
            return "lab_id is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        lab_id = inputs["lab_id"]
        row = await db_execute("SELECT * FROM labs WHERE id = ?", (lab_id,), fetch="one")
        if not row:
            return ToolResult(success=False, error=f"Lab {lab_id} not found")

        now = time.time()
        await db_execute(
            "UPDATE labs SET status = 'stopped', stopped_at = ?, updated_at = ? WHERE id = ?",
            (now, now, lab_id),
        )

        self.log_action("stop_lab", row["name"])
        return ToolResult(success=True, data={"id": lab_id, "status": "stopped", "stopped_at": now})


class LabDeleteTool(BaseTool):
    """Delete a lab."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.lab.delete",
            description="Delete a security assessment lab.",
            category="security",
            risk_level=RiskLevel.HIGH,
            requires_confirmation=True,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "lab_id": {"type": "string", "description": "Lab ID to delete"},
                },
                "required": ["lab_id"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("lab_id"):
            return "lab_id is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        lab_id = inputs["lab_id"]
        await db_execute("DELETE FROM labs WHERE id = ?", (lab_id,))
        self.log_action("delete_lab", lab_id)
        return ToolResult(success=True, data={"deleted": lab_id})


def register_lab_tools(registry: Any) -> None:
    """Register lab tools."""
    registry.register(LabCreateTool())
    registry.register(LabStatusTool())
    registry.register(LabStartTool())
    registry.register(LabStopTool())
    registry.register(LabDeleteTool())
