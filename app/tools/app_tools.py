"""Application management tools — open applications, list running apps."""
from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from loguru import logger

from .base import BaseTool, ToolResult, ToolSpec, RiskLevel


class OpenAppTool(BaseTool):
    """Open an application or file with the default handler."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="app.open",
            description="Open an application or file with the default system handler.",
            category="applications",
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            timeout=10,
            input_schema={
                "target": {"type": "string", "required": True},
                "method": {"type": "string"},  # "xdg-open", "flatpak", "snap"
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("target"):
            return "target is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        target = inputs["target"]
        method = inputs.get("method", "xdg-open")

        try:
            proc = await asyncio.create_subprocess_exec(
                method, target,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            # Don't wait — xdg-open returns immediately
            self.log_action("open", target)
            return ToolResult(success=True, data={"target": target, "method": method, "pid": proc.pid})
        except FileNotFoundError:
            return ToolResult(success=False, error=f"Command not found: {method}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ListWindowsTool(BaseTool):
    """List visible application windows."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="app.list_windows",
            description="List visible application windows using xdotool.",
            category="applications",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10,
            input_schema={},
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                "xdotool", "search", "--name", "",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            wids = [w.strip() for w in stdout.decode().strip().split("\n") if w.strip()]

            windows = []
            for wid in wids[:50]:  # Limit to 50
                try:
                    name_proc = await asyncio.create_subprocess_exec(
                        "xdotool", "getwindowname", wid,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    name_out, _ = await name_proc.communicate()
                    name = name_out.decode().strip()
                    if name:
                        windows.append({"wid": wid, "name": name})
                except Exception:
                    continue

            return ToolResult(success=True, data={"windows": windows, "count": len(windows)})
        except FileNotFoundError:
            return ToolResult(success=False, error="xdotool not installed")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


def register_app_tools(reg) -> None:
    """Register all application tools."""
    for tool_cls in [OpenAppTool, ListWindowsTool]:
        reg.register(tool_cls())
