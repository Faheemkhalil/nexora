"""Crash reporting system for NEXORA.

Captures unhandled exceptions, stores crash reports locally,
and provides export/diagnostic capabilities.
"""
from __future__ import annotations

import json
import time
import traceback
import uuid
import sys
from typing import Any

from loguru import logger

from .db import execute as db_execute


def _ensure_table() -> None:
    """Create crash report tables."""
    import asyncio

    async def _create():
        await db_execute("""
            CREATE TABLE IF NOT EXISTS crash_reports (
                id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                traceback TEXT DEFAULT '',
                component TEXT DEFAULT 'unknown',
                python_version TEXT DEFAULT '',
                platform TEXT DEFAULT '',
                memory_mb REAL DEFAULT 0,
                context TEXT DEFAULT '{}',
                reported INTEGER DEFAULT 0
            )
        """)

    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pool.submit(asyncio.run, _create()).result(timeout=5)
    except RuntimeError:
        asyncio.run(_create())


class CrashReporter:
    """Captures and manages crash reports."""

    def __init__(self) -> None:
        _ensure_table()
        self._pending: list[dict[str, Any]] = []

    def capture_exception(self, exc: Exception, component: str = "unknown",
                          context: dict[str, Any] | None = None) -> str:
        """Capture an exception and store it as a crash report.

        Returns the crash report ID.
        """
        import platform as _platform
        import os

        report_id = f"crash_{uuid.uuid4().hex[:8]}"
        now = time.time()

        # Gather system info
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 * 1024)
        except Exception:
            memory_mb = 0.0

        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

        report = {
            "id": report_id,
            "timestamp": now,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:2000],
            "traceback": tb_str[:5000],
            "component": component,
            "python_version": sys.version.split()[0],
            "platform": f"{_platform.system()} {_platform.release()}",
            "memory_mb": round(memory_mb, 1),
            "context": json.dumps(context or {}),
            "reported": 0,
        }

        # Store in DB
        async def _insert():
            await db_execute(
                """INSERT INTO crash_reports
                   (id, timestamp, error_type, error_message, traceback, component,
                    python_version, platform, memory_mb, context, reported)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (
                    report["id"], report["timestamp"], report["error_type"],
                    report["error_message"], report["traceback"], report["component"],
                    report["python_version"], report["platform"],
                    report["memory_mb"], report["context"],
                ),
            )

        self._run_async(_insert())
        logger.error(f"Crash captured: {report['error_type']} in {component} ({report_id})")
        return report_id

    def get_reports(self, limit: int = 50, component: str | None = None) -> list[dict[str, Any]]:
        """Get crash reports."""
        if component:
            rows = self._run_async(
                db_execute(
                    "SELECT * FROM crash_reports WHERE component = ? ORDER BY timestamp DESC LIMIT ?",
                    (component, limit),
                    fetch="all",
                )
            )
        else:
            rows = self._run_async(
                db_execute(
                    "SELECT * FROM crash_reports ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                    fetch="all",
                )
            )

        return [self._row_to_dict(r) for r in (rows or [])]

    def get_crash_stats(self) -> dict[str, Any]:
        """Get crash report statistics."""
        rows = self._run_async(
            db_execute("SELECT COUNT(*) as total FROM crash_reports", fetch="all")
        )
        total = rows[0]["total"] if rows else 0

        rows = self._run_async(
            db_execute(
                "SELECT component, COUNT(*) as count FROM crash_reports GROUP BY component ORDER BY count DESC",
                fetch="all",
            )
        )
        by_component = {r["component"]: r["count"] for r in (rows or [])}

        rows = self._run_async(
            db_execute(
                "SELECT error_type, COUNT(*) as count FROM crash_reports GROUP BY error_type ORDER BY count DESC LIMIT 10",
                fetch="all",
            )
        )
        by_type = {r["error_type"]: r["count"] for r in (rows or [])}

        # Recent crashes (last 24h)
        cutoff = time.time() - 86400
        rows = self._run_async(
            db_execute(
                "SELECT COUNT(*) as count FROM crash_reports WHERE timestamp > ?",
                (cutoff,),
                fetch="all",
            )
        )
        recent = rows[0]["count"] if rows else 0

        return {
            "total_crashes": total,
            "recent_24h": recent,
            "by_component": by_component,
            "by_error_type": by_type,
            "last_crash": self._run_async(
                db_execute(
                    "SELECT timestamp FROM crash_reports ORDER BY timestamp DESC LIMIT 1",
                    fetch="all",
                )
            )[0]["timestamp"] if total > 0 else None,
        }

    def mark_reported(self, report_id: str) -> None:
        """Mark a crash report as reported to external service."""
        async def _update():
            await db_execute(
                "UPDATE crash_reports SET reported = 1 WHERE id = ?",
                (report_id,),
            )
        self._run_async(_update())

    def delete_report(self, report_id: str) -> bool:
        """Delete a crash report."""
        async def _delete():
            await db_execute("DELETE FROM crash_reports WHERE id = ?", (report_id,))
        self._run_async(_delete())
        return True

    def clear_all(self) -> int:
        """Clear all crash reports. Returns count deleted."""
        rows = self._run_async(
            db_execute("SELECT COUNT(*) as count FROM crash_reports", fetch="all")
        )
        count = rows[0]["count"] if rows else 0
        async def _clear():
            await db_execute("DELETE FROM crash_reports")
        self._run_async(_clear())
        return count

    def _row_to_dict(self, row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "error_type": row["error_type"],
            "error_message": row["error_message"],
            "traceback": row["traceback"],
            "component": row["component"],
            "python_version": row["python_version"],
            "platform": row["platform"],
            "memory_mb": row["memory_mb"],
            "context": json.loads(row["context"] or "{}"),
            "reported": bool(row["reported"]),
        }

    def _run_async(self, coro):
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result(timeout=5)
        except RuntimeError:
            return asyncio.run(coro)
