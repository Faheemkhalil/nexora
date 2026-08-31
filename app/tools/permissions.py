"""Permission manager — handles permission checks, audit logging, emergency stop.

The permission system enforces:
- Risk-based confirmation requirements
- Audit logging for all tool actions
- Emergency stop for active tasks
- Permission policies for tool categories
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from loguru import logger

from .base import RiskLevel
from ..core.db import execute as db_execute


class PermissionManager:
    """Manages tool permissions, audit logging, and emergency stop."""

    def __init__(self) -> None:
        self._emergency_stop = False
        self._active_tasks: dict[str, dict] = {}
        self._policies: dict[str, dict] = {
            "files": {"auto_confirm_safe": True, "require_confirm_above": RiskLevel.MEDIUM},
            "terminal": {"auto_confirm_safe": False, "require_confirm_above": RiskLevel.LOW},
            "system": {"auto_confirm_safe": True, "require_confirm_above": RiskLevel.SAFE},
            "applications": {"auto_confirm_safe": True, "require_confirm_above": RiskLevel.SAFE},
        }

    @property
    def is_emergency_stopped(self) -> bool:
        return self._emergency_stop

    def emergency_stop(self) -> None:
        """Activate emergency stop — all running tasks should be cancelled."""
        self._emergency_stop = True
        logger.warning("EMERGENCY STOP activated")
        # Cancel all active tasks
        for task_id, task in list(self._active_tasks.items()):
            task["cancelled"] = True
            logger.info(f"Cancelled task: {task_id} ({task.get('name', 'unknown')})")

    def reset_emergency_stop(self) -> None:
        """Reset emergency stop."""
        self._emergency_stop = False
        logger.info("Emergency stop reset")

    def register_task(self, task_id: str, name: str, details: dict | None = None) -> None:
        """Register an active task."""
        self._active_tasks[task_id] = {
            "name": name,
            "details": details or {},
            "started_at": time.time(),
            "cancelled": False,
        }

    def unregister_task(self, task_id: str) -> None:
        """Unregister a completed task."""
        self._active_tasks.pop(task_id, None)

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a task has been cancelled."""
        task = self._active_tasks.get(task_id)
        return task.get("cancelled", False) if task else False

    def get_active_tasks(self) -> list[dict]:
        """List all active tasks."""
        return [
            {
                "id": tid,
                "name": t["name"],
                "started_at": t["started_at"],
                "elapsed": round(time.time() - t["started_at"], 1),
            }
            for tid, t in self._active_tasks.items()
            if not t.get("cancelled")
        ]

    def needs_confirmation(self, risk_level: RiskLevel, category: str) -> bool:
        """Determine if a tool action needs user confirmation."""
        if self._emergency_stop:
            return True

        policy = self._policies.get(category, {})
        require_above = policy.get("require_confirm_above", RiskLevel.SAFE)

        risk_order = [RiskLevel.SAFE, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        return risk_order.index(risk_level) > risk_order.index(require_above)

    async def audit_log(
        self,
        action: str,
        resource: str = "",
        outcome: str = "success",
        details: str = "",
    ) -> None:
        """Write an audit log entry."""
        try:
            await db_execute(
                "INSERT INTO audit_logs (id, action, resource, outcome, details, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    action,
                    resource[:500],
                    outcome,
                    details[:500],
                    time.time(),
                ),
            )
        except Exception as e:
            logger.warning(f"Audit log write failed: {e}")

    async def get_audit_logs(self, limit: int = 50) -> list[dict]:
        """Retrieve recent audit logs."""
        try:
            rows = await db_execute(
                "SELECT id, action, resource, outcome, details, timestamp FROM audit_logs ORDER BY timestamp DESC LIMIT ?",
                (limit,),
                fetch="all",
            )
            return rows or []
        except Exception as e:
            logger.warning(f"Audit log read failed: {e}")
            return []


# Global singleton
permissions = PermissionManager()
