"""Test runner backend — run pytest, npm test, and other test frameworks."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Any

from loguru import logger

from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


class RunTestsTool(BaseTool):
    """Run tests using the project's test framework."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.test.run",
            description="Run tests (auto-detects pytest, npm test, go test, etc.).",
            category="coding",
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            timeout=120.0,
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project root path"},
                    "framework": {
                        "type": "string",
                        "enum": ["auto", "pytest", "npm", "cargo"],
                        "description": "Test framework (auto-detect by default)",
                    },
                    "target": {"type": "string", "description": "Specific test file, class, or function"},
                    "verbose": {"type": "boolean", "description": "Verbose output"},
                },
                "required": ["path"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("path"):
            return "path is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        path = inputs["path"]
        framework = inputs.get("framework", "auto")
        target = inputs.get("target", "")
        verbose = inputs.get("verbose", True)

        if framework == "auto":
            framework = self._detect_framework(path)

        cmd = self._build_command(framework, path, target, verbose)
        if not cmd:
            return ToolResult(success=False, error=f"Could not detect test framework in {path}")

        logger.info(f"Running tests: {' '.join(cmd)} in {path}")

        start = time.time()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=path,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            return ToolResult(success=False, error="Test execution timed out (120s)")

        elapsed_ms = (time.time() - start) * 1000
        stdout_str = stdout.decode(errors="replace")
        stderr_str = stderr.decode(errors="replace")
        exit_code = proc.returncode or 0

        # Parse results
        parsed = self._parse_results(framework, stdout_str, stderr_str, exit_code)

        self.log_action("run_tests", path, outcome="success" if exit_code == 0 else "failure")
        return ToolResult(
            success=exit_code == 0,
            data={
                "framework": framework,
                "exit_code": exit_code,
                "elapsed_ms": elapsed_ms,
                "stdout": stdout_str[-5000:],  # Last 5000 chars
                "stderr": stderr_str[-2000:],
                **parsed,
            },
        )

    def _detect_framework(self, path: str) -> str:
        """Auto-detect the test framework."""
        if os.path.exists(os.path.join(path, "package.json")):
            try:
                with open(os.path.join(path, "package.json")) as f:
                    pkg = json.load(f)
                if "test" in pkg.get("scripts", {}):
                    return "npm"
            except Exception:
                pass

        if os.path.exists(os.path.join(path, "Cargo.toml")):
            return "cargo"

        # Check for Python test files
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in {"node_modules", "__pycache__", ".git", "venv"}]
            for f in files:
                if f.startswith("test_") and f.endswith(".py"):
                    return "pytest"
                if f.endswith("_test.py"):
                    return "pytest"

        return "pytest"  # Default

    def _build_command(self, framework: str, path: str, target: str, verbose: bool) -> list[str] | None:
        if framework == "pytest":
            cmd = ["python3", "-m", "pytest"]
            if verbose:
                cmd.append("-v")
            if target:
                cmd.append(target)
            cmd.extend(["--tb=short", "-q"])
            return cmd

        elif framework == "npm":
            return ["npm", "test"]

        elif framework == "cargo":
            return ["cargo", "test"]

        return None

    def _parse_results(self, framework: str, stdout: str, stderr: str, exit_code: int) -> dict:
        """Parse test results from output."""
        result: dict[str, Any] = {"passed": 0, "failed": 0, "skipped": 0, "total": 0}

        if framework == "pytest":
            # Parse "X passed, Y failed, Z skipped" line
            summary = re.search(r"(\d+) passed.*?(\d+) failed.*?(\d+) skipped", stdout)
            if summary:
                result["passed"] = int(summary.group(1))
                result["failed"] = int(summary.group(2))
                result["skipped"] = int(summary.group(3))
                result["total"] = result["passed"] + result["failed"] + result["skipped"]
            else:
                passed = re.search(r"(\d+) passed", stdout)
                failed = re.search(r"(\d+) failed", stdout)
                skipped = re.search(r"(\d+) skipped", stdout)
                result["passed"] = int(passed.group(1)) if passed else 0
                result["failed"] = int(failed.group(1)) if failed else 0
                result["skipped"] = int(skipped.group(1)) if skipped else 0
                result["total"] = result["passed"] + result["failed"] + result["skipped"]

            # Parse individual failures
            failures = []
            failure_blocks = re.findall(r"(FAILED .+?)(?=FAILED|\Z)", stdout, re.DOTALL)
            for block in failure_blocks[:10]:
                failures.append(block.strip()[:200])
            result["failure_details"] = failures

        elif framework == "npm":
            result["output"] = stdout[-2000:]

        elif framework == "cargo":
            result["output"] = stdout[-2000:]

        return result


def register_test_tools(registry: Any) -> None:
    """Register test runner tools."""
    registry.register(RunTestsTool())
