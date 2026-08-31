"""Findings system — create, list, update, and filter security findings."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from loguru import logger

from ..core.db import execute as db_execute
from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


async def _ensure_table() -> None:
    """Create findings table with the new schema, replacing the old one if needed."""
    # Check if old-style table exists (has 'resolved' column instead of 'status')
    try:
        existing = await db_execute("PRAGMA table_info(findings)", fetch="all")
        columns = {r["name"] for r in (existing or [])} if existing else set()
        if columns and "status" not in columns:
            # Old schema — drop and recreate
            await db_execute("DROP TABLE IF EXISTS findings")
    except Exception:
        pass

    await db_execute("""
        CREATE TABLE IF NOT EXISTS findings (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            affected_asset TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            evidence TEXT DEFAULT '',
            impact TEXT DEFAULT '',
            reproduction TEXT DEFAULT '',
            remediation TEXT DEFAULT '',
            references_json TEXT DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'open',
            category TEXT DEFAULT 'general',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    await db_execute("""
        CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity)
    """)
    await db_execute("""
        CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status)
    """)


class CreateFindingTool(BaseTool):
    """Create a new security finding."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.findings.create",
            description="Create a new security finding with severity, evidence, and remediation.",
            category="security",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Finding title"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low", "info"],
                        "description": "Severity level",
                    },
                    "affected_asset": {"type": "string", "description": "Affected asset/URL"},
                    "description": {"type": "string", "description": "Detailed description"},
                    "evidence": {"type": "string", "description": "Evidence (screenshots, logs, requests)"},
                    "impact": {"type": "string", "description": "Impact description"},
                    "reproduction": {"type": "string", "description": "Steps to reproduce"},
                    "remediation": {"type": "string", "description": "Remediation recommendation"},
                    "category": {"type": "string", "description": "Category (web, mobile, code, config)"},
                },
                "required": ["title", "severity"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("title"):
            return "title is required"
        severity = inputs.get("severity", "info")
        if severity not in ("critical", "high", "medium", "low", "info"):
            return f"Invalid severity: {severity}"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        finding_id = str(uuid.uuid4())
        now = time.time()

        await db_execute(
            """INSERT INTO findings
            (id, title, severity, affected_asset, description, evidence, impact,
             reproduction, remediation, references_json, status, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                finding_id,
                inputs["title"],
                inputs.get("severity", "info"),
                inputs.get("affected_asset", ""),
                inputs.get("description", ""),
                inputs.get("evidence", ""),
                inputs.get("impact", ""),
                inputs.get("reproduction", ""),
                inputs.get("remediation", ""),
                json.dumps(inputs.get("references", [])),
                "open",
                inputs.get("category", "general"),
                now,
                now,
            ),
        )

        self.log_action("create_finding", inputs["title"], details=f"severity={inputs.get('severity')}")
        return ToolResult(
            success=True,
            data={"id": finding_id, "title": inputs["title"], "severity": inputs.get("severity", "info")},
        )


class ListFindingsTool(BaseTool):
    """List security findings with optional filtering."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.findings.list",
            description="List security findings, optionally filtered by severity or status.",
            category="security",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "description": "Filter by severity"},
                    "status": {"type": "string", "description": "Filter by status"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
            },
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        query = "SELECT * FROM findings WHERE 1=1"
        params: list[Any] = []

        severity = inputs.get("severity")
        if severity:
            query += " AND severity = ?"
            params.append(severity)

        status = inputs.get("status")
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"
        limit = inputs.get("limit", 100)
        query += " LIMIT ?"
        params.append(limit)

        rows = await db_execute(query, tuple(params), fetch="all")
        findings = []
        for row in (rows or []):
            findings.append({
                "id": row["id"],
                "title": row["title"],
                "severity": row["severity"],
                "affected_asset": row["affected_asset"],
                "description": row["description"],
                "evidence": row["evidence"],
                "impact": row["impact"],
                "reproduction": row["reproduction"],
                "remediation": row["remediation"],
                "references": json.loads(row["references_json"] or "[]"),
                "status": row["status"],
                "category": row["category"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            })

        self.log_action("list_findings", details=f"count={len(findings)}")
        return ToolResult(
            success=True,
            data={"findings": findings, "total": len(findings)},
        )


class UpdateFindingTool(BaseTool):
    """Update a security finding's status, severity, or details."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.findings.update",
            description="Update a security finding (status, severity, details).",
            category="security",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Finding ID"},
                    "status": {"type": "string", "enum": ["open", "confirmed", "fixed", "false_positive", "accepted"], "description": "New status"},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "info"], "description": "New severity"},
                    "remediation": {"type": "string", "description": "Updated remediation"},
                },
                "required": ["id"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("id"):
            return "id is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        finding_id = inputs["id"]
        now = time.time()

        # Check existence
        row = await db_execute("SELECT id FROM findings WHERE id = ?", (finding_id,), fetch="one")
        if not row:
            return ToolResult(success=False, error=f"Finding {finding_id} not found")

        updates = ["updated_at = ?"]
        params: list[Any] = [now]

        if "status" in inputs:
            updates.append("status = ?")
            params.append(inputs["status"])
        if "severity" in inputs:
            updates.append("severity = ?")
            params.append(inputs["severity"])
        if "remediation" in inputs:
            updates.append("remediation = ?")
            params.append(inputs["remediation"])

        params.append(finding_id)
        await db_execute(f"UPDATE findings SET {', '.join(updates)} WHERE id = ?", tuple(params))

        self.log_action("update_finding", finding_id)
        return ToolResult(success=True, data={"id": finding_id, "updated": True})


class DeleteFindingTool(BaseTool):
    """Delete a security finding."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.findings.delete",
            description="Delete a security finding.",
            category="security",
            risk_level=RiskLevel.LOW,
            requires_confirmation=True,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Finding ID"},
                },
                "required": ["id"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("id"):
            return "id is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        finding_id = inputs["id"]
        await db_execute("DELETE FROM findings WHERE id = ?", (finding_id,))
        self.log_action("delete_finding", finding_id)
        return ToolResult(success=True, data={"deleted": finding_id})


class FindingsSummaryTool(BaseTool):
    """Get a summary of findings by severity and status."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.findings.summary",
            description="Get a summary of findings counts by severity and status.",
            category="security",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={"type": "object", "properties": {}},
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()

        severity_rows = await db_execute(
            "SELECT severity, COUNT(*) as count FROM findings GROUP BY severity",
            fetch="all",
        )
        status_rows = await db_execute(
            "SELECT status, COUNT(*) as count FROM findings GROUP BY status",
            fetch="all",
        )
        total_rows = await db_execute("SELECT COUNT(*) as count FROM findings", fetch="one")

        by_severity = {r["severity"]: r["count"] for r in (severity_rows or [])}
        by_status = {r["status"]: r["count"] for r in (status_rows or [])}
        total = total_rows["count"] if total_rows else 0

        return ToolResult(
            success=True,
            data={
                "total": total,
                "by_severity": by_severity,
                "by_status": by_status,
                "critical": by_severity.get("critical", 0),
                "high": by_severity.get("high", 0),
                "medium": by_severity.get("medium", 0),
                "low": by_severity.get("low", 0),
                "info": by_severity.get("info", 0),
            },
        )


def register_finding_tools(registry: Any) -> None:
    """Register all finding tools."""
    registry.register(CreateFindingTool())
    registry.register(ListFindingsTool())
    registry.register(UpdateFindingTool())
    registry.register(DeleteFindingTool())
    registry.register(FindingsSummaryTool())
