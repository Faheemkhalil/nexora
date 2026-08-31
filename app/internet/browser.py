"""Browser integration tool — open URLs in the system browser."""

from __future__ import annotations

import asyncio
import platform
import subprocess
from typing import Any

from loguru import logger

from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


async def _open_in_browser(url: str) -> bool:
    """Open a URL in the system's default browser."""
    system = platform.system()

    if system == "Linux":
        # Try xdg-open first, then sensible-browser
        for cmd in [["xdg-open", url], ["sensible-browser", url]]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.communicate(), timeout=5)
                if proc.returncode == 0:
                    return True
            except (FileNotFoundError, asyncio.TimeoutError):
                continue
    elif system == "Darwin":
        try:
            proc = await asyncio.create_subprocess_exec(
                "open", url,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except (FileNotFoundError, asyncio.TimeoutError):
            pass
    elif system == "Windows":
        try:
            proc = await asyncio.create_subprocess_exec(
                "cmd", "/c", "start", url.replace("&", "^&"),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except (FileNotFoundError, asyncio.TimeoutError):
            pass

    return False


class OpenBrowserTool(BaseTool):
    """Open a URL in the system browser."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="internet.open",
            description="Open a URL in the system's default web browser.",
            category="internet",
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            timeout=10.0,
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to open"},
                },
                "required": ["url"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        url = inputs.get("url", "")
        if not url:
            return "url is required"
        if not url.startswith(("http://", "https://", "file://")):
            return "url must start with http://, https://, or file://"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        url = inputs["url"]

        try:
            opened = await _open_in_browser(url)
            self.log_action("open_browser", url, outcome="success" if opened else "failure")
            if opened:
                return ToolResult(success=True, data={"url": url, "opened": True})
            else:
                return ToolResult(
                    success=False,
                    error="Could not open browser. The URL would be: " + url,
                    data={"url": url, "opened": False},
                )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to open browser: {e}")


def register_browser_tools(registry: Any) -> None:
    """Register browser tools."""
    registry.register(OpenBrowserTool())
