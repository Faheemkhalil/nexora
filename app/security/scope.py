"""Scope management — validate targets against defined scope boundaries."""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from ..core.db import execute as db_execute
from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


async def _ensure_table() -> None:
    await db_execute("""
        CREATE TABLE IF NOT EXISTS scope_rules (
            id TEXT PRIMARY KEY,
            lab_id TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            pattern TEXT NOT NULL,
            action TEXT NOT NULL DEFAULT 'allow',
            description TEXT DEFAULT '',
            created_at REAL NOT NULL
        )
    """)


def _match_ip(target: str, pattern: str) -> bool:
    """Check if an IP matches a CIDR range or exact match."""
    try:
        target_ip = ipaddress.ip_address(target)
        if "/" in pattern:
            network = ipaddress.ip_network(pattern, strict=False)
            return target_ip in network
        return target_ip == ipaddress.ip_address(pattern)
    except ValueError:
        return False


def _match_domain(target: str, pattern: str) -> bool:
    """Check if a domain matches a pattern (exact, subdomain, or wildcard)."""
    target = target.lower().strip()
    pattern = pattern.lower().strip()

    if pattern.startswith("*."):
        # Wildcard: *.example.com matches sub.example.com
        suffix = pattern[1:]
        return target == suffix[1:] or target.endswith(suffix)
    return target == pattern


def _match_url(target: str, pattern: str) -> bool:
    """Check if a URL matches a pattern."""
    try:
        parsed = urlparse(target)
        host = parsed.hostname or ""
        return _match_domain(host, pattern)
    except Exception:
        return False


def _match_port(target_port: int, pattern: str) -> bool:
    """Check if a port matches a pattern (exact, range, or list)."""
    pattern = pattern.strip()
    if "-" in pattern:
        parts = pattern.split("-", 1)
        try:
            return int(parts[0]) <= target_port <= int(parts[1])
        except ValueError:
            return False
    if "," in pattern:
        return str(target_port) in [p.strip() for p in pattern.split(",")]
    return str(target_port) == pattern


class ScopeCheckTool(BaseTool):
    """Check if a target is within the defined scope."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.scope.check",
            description="Check if a target (IP, domain, URL) is within the authorized scope.",
            category="security",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=5.0,
            input_schema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Target to check (IP, domain, URL)"},
                    "lab_id": {"type": "string", "description": "Lab ID to check scope against"},
                    "port": {"type": "integer", "description": "Port number (optional)"},
                },
                "required": ["target"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("target"):
            return "target is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        target = inputs["target"]
        lab_id = inputs.get("lab_id")
        port = inputs.get("port")

        # Get scope rules
        if lab_id:
            rows = await db_execute(
                "SELECT * FROM scope_rules WHERE lab_id = ?", (lab_id,), fetch="all"
            )
        else:
            rows = await db_execute("SELECT * FROM scope_rules", fetch="all")

        if not rows:
            return ToolResult(
                success=True,
                data={"in_scope": True, "reason": "No scope rules defined — all targets allowed"},
            )

        allowed = False
        matched_rule = None

        for rule in (rows or []):
            rule_type = rule["rule_type"]
            pattern = rule["pattern"]
            in_scope = False

            if rule_type == "ip":
                in_scope = _match_ip(target, pattern)
            elif rule_type == "domain":
                in_scope = _match_domain(target, pattern)
            elif rule_type == "url":
                in_scope = _match_url(target, pattern)
            elif rule_type == "port" and port is not None:
                in_scope = _match_port(port, pattern)

            if in_scope:
                if rule["action"] == "allow":
                    allowed = True
                    matched_rule = rule
                    break
                elif rule["action"] == "deny":
                    allowed = False
                    matched_rule = rule
                    break

        reason = "Matched rule" if matched_rule else "No matching rules"
        self.log_action("scope_check", target, outcome="allowed" if allowed else "denied")
        return ToolResult(
            success=True,
            data={
                "target": target,
                "in_scope": allowed,
                "reason": reason,
                "matched_rule": {
                    "type": matched_rule["rule_type"],
                    "pattern": matched_rule["pattern"],
                    "action": matched_rule["action"],
                } if matched_rule else None,
            },
        )


class ScopeAddRuleTool(BaseTool):
    """Add a scope rule (allow/deny IP, domain, URL, or port)."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.scope.add",
            description="Add a scope rule (allow/deny IP, domain, URL, or port pattern).",
            category="security",
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "lab_id": {"type": "string", "description": "Lab ID"},
                    "rule_type": {
                        "type": "string",
                        "enum": ["ip", "domain", "url", "port"],
                        "description": "Rule type",
                    },
                    "pattern": {"type": "string", "description": "Pattern (CIDR, domain, *.domain, port-range)"},
                    "action": {"type": "string", "enum": ["allow", "deny"], "description": "Action"},
                    "description": {"type": "string", "description": "Rule description"},
                },
                "required": ["lab_id", "rule_type", "pattern", "action"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        for field in ("lab_id", "rule_type", "pattern", "action"):
            if not inputs.get(field):
                return f"{field} is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        import uuid, time
        rule_id = str(uuid.uuid4())[:8]

        await db_execute(
            """INSERT INTO scope_rules (id, lab_id, rule_type, pattern, action, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                rule_id,
                inputs["lab_id"],
                inputs["rule_type"],
                inputs["pattern"],
                inputs["action"],
                inputs.get("description", ""),
                time.time(),
            ),
        )

        self.log_action("add_scope_rule", details=f"type={inputs['rule_type']} pattern={inputs['pattern']}")
        return ToolResult(
            success=True,
            data={"id": rule_id, "type": inputs["rule_type"], "pattern": inputs["pattern"], "action": inputs["action"]},
        )


class ScopeListRulesTool(BaseTool):
    """List all scope rules for a lab."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.scope.list",
            description="List scope rules for a lab.",
            category="security",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "lab_id": {"type": "string", "description": "Lab ID"},
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
        rows = await db_execute(
            "SELECT * FROM scope_rules WHERE lab_id = ? ORDER BY created_at",
            (inputs["lab_id"],),
            fetch="all",
        )
        rules = [
            {
                "id": r["id"],
                "type": r["rule_type"],
                "pattern": r["pattern"],
                "action": r["action"],
                "description": r["description"],
            }
            for r in (rows or [])
        ]
        return ToolResult(success=True, data={"rules": rules, "total": len(rules)})


class ScopeDeleteRuleTool(BaseTool):
    """Delete a scope rule."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="security.scope.delete",
            description="Delete a scope rule.",
            category="security",
            risk_level=RiskLevel.LOW,
            requires_confirmation=True,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "Rule ID"},
                },
                "required": ["rule_id"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("rule_id"):
            return "rule_id is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        await _ensure_table()
        await db_execute("DELETE FROM scope_rules WHERE id = ?", (inputs["rule_id"],))
        return ToolResult(success=True, data={"deleted": inputs["rule_id"]})


def register_scope_tools(registry: Any) -> None:
    """Register scope tools."""
    registry.register(ScopeCheckTool())
    registry.register(ScopeAddRuleTool())
    registry.register(ScopeListRulesTool())
    registry.register(ScopeDeleteRuleTool())
