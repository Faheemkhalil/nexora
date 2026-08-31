"""Project manager — manage coding workspaces and recent projects."""

from __future__ import annotations

import os
import time
from typing import Any

from loguru import logger

from ..core.db import execute as db_execute
from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


class ProjectListTool(BaseTool):
    """List recently opened projects."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.projects.list",
            description="List recently opened projects.",
            category="coding",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {},
            },
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            rows = await db_execute(
                "SELECT key, value FROM settings WHERE key LIKE 'project_%' ORDER BY key",
                fetch="all",
            )
            projects = []
            if rows:
                import json
                for row in rows:
                    try:
                        proj = json.loads(row["value"])
                        proj["id"] = row["key"].replace("project_", "")
                        projects.append(proj)
                    except Exception:
                        continue

            self.log_action("list_projects", details=f"count={len(projects)}")
            return ToolResult(success=True, data={"projects": projects})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ProjectOpenTool(BaseTool):
    """Open/register a project workspace."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.projects.open",
            description="Open/register a project directory as a workspace.",
            category="coding",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project directory path"},
                    "name": {"type": "string", "description": "Project display name"},
                },
                "required": ["path"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import json
        import uuid

        path = os.path.abspath(inputs["path"])
        name = inputs.get("name", os.path.basename(path))

        if not os.path.isdir(path):
            return ToolResult(success=False, error=f"Directory not found: {path}")

        # Detect project type
        project_type = "unknown"
        if os.path.exists(os.path.join(path, "package.json")):
            project_type = "node"
        elif os.path.exists(os.path.join(path, "requirements.txt")) or os.path.exists(os.path.join(path, "setup.py")) or os.path.exists(os.path.join(path, "pyproject.toml")):
            project_type = "python"
        elif os.path.exists(os.path.join(path, "Cargo.toml")):
            project_type = "rust"
        elif os.path.exists(os.path.join(path, "go.mod")):
            project_type = "go"

        # Check for git
        is_git = os.path.isdir(os.path.join(path, ".git"))

        proj_id = str(uuid.uuid4())[:8]
        proj_data = {
            "path": path,
            "name": name,
            "type": project_type,
            "is_git": is_git,
            "opened_at": time.time(),
        }

        await db_execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (f"project_{proj_id}", json.dumps(proj_data)),
        )

        self.log_action("open_project", path)
        return ToolResult(success=True, data={"id": proj_id, **proj_data})


def register_project_tools(registry: Any) -> None:
    """Register project management tools."""
    registry.register(ProjectListTool())
    registry.register(ProjectOpenTool())
