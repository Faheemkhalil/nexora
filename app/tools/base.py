"""Base tool abstraction — every tool in NEXORA subclasses this.

Each tool declares:
- Name, description
- Required inputs
- Permissions required
- Risk level
- Whether confirmation is needed
- Timeout
- Output format
"""
from __future__ import annotations

import enum
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any


class RiskLevel(str, enum.Enum):
    """Risk classification for tool actions."""
    SAFE = "safe"           # Read-only, no side effects
    LOW = "low"             # Minor write, reversible
    MEDIUM = "medium"       # Write/modify, may need confirmation
    HIGH = "high"           # Destructive or system-level, requires confirmation
    CRITICAL = "critical"   # Privileged/destructive, always requires confirmation


@dataclass
class ToolResult:
    """Structured result from tool execution."""
    success: bool
    data: Any = None
    error: str | None = None
    details: str | None = None
    execution_time_ms: float = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("details", None)
        return d


@dataclass
class ToolSpec:
    """Specification for a registered tool — used for discovery and permission checks."""
    name: str
    description: str
    category: str
    risk_level: RiskLevel
    requires_confirmation: bool
    timeout: float  # seconds
    input_schema: dict[str, Any]  # JSON Schema for inputs
    output_format: str = "json"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        return d


class BaseTool(ABC):
    """Abstract base class for all NEXORA tools."""

    @abstractmethod
    def spec(self) -> ToolSpec:
        """Return the tool specification."""
        ...

    @abstractmethod
    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        """Execute the tool with given inputs and return a result."""
        ...

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        """Validate inputs. Return error string if invalid, None if ok."""
        return None

    def log_action(self, action: str, resource: str = "", outcome: str = "success", details: str = "") -> None:
        """Log a tool action for audit purposes."""
        from loguru import logger
        logger.info(f"Tool [{self.spec().name}] {action}: {resource} ({outcome})")
