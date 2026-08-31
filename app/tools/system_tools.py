"""System information tools — platform, CPU, memory, disk, network."""
from __future__ import annotations

import os
import platform
import socket
from typing import Any

from .base import BaseTool, ToolResult, ToolSpec, RiskLevel


class SystemInfoTool(BaseTool):
    """Get comprehensive system information."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="system.info",
            description="Get system information: OS, CPU, memory, disk, network.",
            category="system",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10,
            input_schema={},
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import psutil

        info = {
            "os": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python": platform.python_version(),
            },
            "cpu": {
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
                "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None,
                "usage_percent": psutil.cpu_percent(interval=0.5),
            },
            "memory": _get_memory_info(),
            "disk": _get_disk_info(),
            "network": _get_network_info(),
            "hostname": socket.gethostname(),
        }

        self.log_action("system_info")
        return ToolResult(success=True, data=info)


class DiskInfoTool(BaseTool):
    """Get disk usage for specific paths."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="system.disk",
            description="Get disk usage for a specific path.",
            category="system",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=5,
            input_schema={"path": {"type": "string", "required": True}},
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import shutil
        path = inputs.get("path", "/")
        try:
            usage = shutil.disk_usage(path)
            return ToolResult(success=True, data={
                "path": path,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent_used": round(usage.used / usage.total * 100, 1),
            })
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ProcessListTool(BaseTool):
    """List running processes."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="system.processes",
            description="List running processes with CPU/memory usage.",
            category="system",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=10,
            input_schema={"max_results": {"type": "integer"}},
        )

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import psutil

        max_results = inputs.get("max_results", 30)
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                info = proc.info
                processes.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu_percent": round(info["cpu_percent"] or 0, 1),
                    "memory_percent": round(info["memory_percent"] or 0, 1),
                    "status": info["status"],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by CPU usage
        processes.sort(key=lambda p: p["cpu_percent"], reverse=True)
        return ToolResult(success=True, data={"processes": processes[:max_results], "total": len(processes)})


def _get_memory_info() -> dict:
    """Get memory information."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "percent_used": mem.percent,
        }
    except ImportError:
        return {"error": "psutil not installed"}


def _get_disk_info() -> dict:
    """Get disk information."""
    try:
        import psutil
        partitions = []
        for p in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(p.mountpoint)
                partitions.append({
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                })
            except PermissionError:
                continue
        return {"partitions": partitions}
    except ImportError:
        return {"error": "psutil not installed"}


def _get_network_info() -> dict:
    """Get network information."""
    try:
        hostname = socket.gethostname()
        try:
            ip = socket.gethostbyname(hostname)
        except socket.gaierror:
            ip = "unknown"
        return {"hostname": hostname, "ip": ip}
    except Exception:
        return {"error": "Could not get network info"}


def register_system_tools(reg) -> None:
    """Register all system tools."""
    for tool_cls in [SystemInfoTool, DiskInfoTool, ProcessListTool]:
        reg.register(tool_cls())
