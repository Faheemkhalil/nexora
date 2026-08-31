"""Analytics and performance dashboard for NEXORA.

Tracks usage metrics, system performance, feature adoption,
and provides a unified health overview.
"""
from __future__ import annotations

import json
import time
import os
from typing import Any

from loguru import logger

from .db import execute as db_execute


def _ensure_table() -> None:
    """Create analytics tables."""
    import asyncio

    async def _create():
        await db_execute("""
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                component TEXT DEFAULT '',
                details TEXT DEFAULT '{}',
                timestamp REAL NOT NULL
            )
        """)
        await db_execute("""
            CREATE TABLE IF NOT EXISTS analytics_sessions (
                id TEXT PRIMARY KEY,
                started_at REAL,
                ended_at REAL,
                events_count INTEGER DEFAULT 0,
                memory_peak_mb REAL DEFAULT 0
            )
        """)

    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pool.submit(asyncio.run, _create()).result(timeout=5)
    except RuntimeError:
        asyncio.run(_create())


class AnalyticsManager:
    """Tracks and reports usage analytics."""

    def __init__(self) -> None:
        _ensure_table()
        self._session_id: str | None = None
        self._session_start: float = time.time()

    def start_session(self) -> str:
        """Start a new analytics session."""
        import uuid
        self._session_id = f"ses_{uuid.uuid4().hex[:8]}"
        self._session_start = time.time()

        async def _insert():
            await db_execute(
                "INSERT INTO analytics_sessions (id, started_at) VALUES (?, ?)",
                (self._session_id, self._session_start),
            )
        self._run_async(_insert())
        return self._session_id

    def end_session(self) -> None:
        """End the current session."""
        if not self._session_id:
            return
        now = time.time()
        async def _update():
            await db_execute(
                "UPDATE analytics_sessions SET ended_at = ?, events_count = (SELECT COUNT(*) FROM analytics_events WHERE timestamp > ?) WHERE id = ?",
                (now, self._session_start, self._session_id),
            )
        self._run_async(_update())

    def track_event(self, event_type: str, component: str = "",
                    details: dict[str, Any] | None = None) -> None:
        """Track an analytics event."""
        now = time.time()

        async def _insert():
            await db_execute(
                "INSERT INTO analytics_events (event_type, component, details, timestamp) VALUES (?, ?, ?, ?)",
                (event_type, component, json.dumps(details or {}), now),
            )
        self._run_async(_insert())

    def get_usage_stats(self) -> dict[str, Any]:
        """Get overall usage statistics."""
        # Total events
        rows = self._run_async(
            db_execute("SELECT COUNT(*) as count FROM analytics_events", fetch="all")
        )
        total_events = rows[0]["count"] if rows else 0

        # Total sessions
        rows = self._run_async(
            db_execute("SELECT COUNT(*) as count FROM analytics_sessions", fetch="all")
        )
        total_sessions = rows[0]["count"] if rows else 0

        # Events by type (top 10)
        rows = self._run_async(
            db_execute(
                """SELECT event_type, COUNT(*) as count
                   FROM analytics_events GROUP BY event_type
                   ORDER BY count DESC LIMIT 10""",
                fetch="all",
            )
        )
        events_by_type = {r["event_type"]: r["count"] for r in (rows or [])}

        # Events by component
        rows = self._run_async(
            db_execute(
                """SELECT component, COUNT(*) as count
                   FROM analytics_events WHERE component != ''
                   GROUP BY component ORDER BY count DESC LIMIT 10""",
                fetch="all",
            )
        )
        events_by_component = {r["component"]: r["count"] for r in (rows or [])}

        # Events per hour (last 24h)
        cutoff = time.time() - 86400
        rows = self._run_async(
            db_execute(
                """SELECT CAST(timestamp / 3600 AS INTEGER) as hour, COUNT(*) as count
                   FROM analytics_events WHERE timestamp > ?
                   GROUP BY hour ORDER BY hour""",
                (cutoff,),
                fetch="all",
            )
        )
        hourly = [{"hour": r["hour"], "count": r["count"]} for r in (rows or [])]

        return {
            "total_events": total_events,
            "total_sessions": total_sessions,
            "events_by_type": events_by_type,
            "events_by_component": events_by_component,
            "hourly_activity": hourly,
        }

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get system performance metrics."""
        import psutil

        process = psutil.Process(os.getpid())
        mem = process.memory_info()
        cpu = process.cpu_percent(interval=0.1)

        # System-wide
        sys_mem = psutil.virtual_memory()
        sys_cpu = psutil.cpu_percent(interval=0.1)

        return {
            "process": {
                "pid": os.getpid(),
                "memory_mb": round(mem.rss / (1024 * 1024), 1),
                "memory_vms_mb": round(mem.vms / (1024 * 1024), 1),
                "cpu_percent": cpu,
                "threads": process.num_threads(),
                "uptime_seconds": round(time.time() - process.create_time(), 0),
            },
            "system": {
                "cpu_percent": sys_cpu,
                "memory_total_gb": round(sys_mem.total / (1024**3), 1),
                "memory_used_gb": round(sys_mem.used / (1024**3), 1),
                "memory_percent": sys_mem.percent,
                "cpu_count": psutil.cpu_count(),
            },
        }

    def get_feature_adoption(self) -> dict[str, Any]:
        """Get feature adoption metrics."""
        rows = self._run_async(
            db_execute(
                """SELECT component, COUNT(DISTINCT event_type) as feature_count,
                          COUNT(*) as usage_count
                   FROM analytics_events
                   WHERE component != ''
                   GROUP BY component ORDER BY usage_count DESC""",
                fetch="all",
            )
        )

        features = []
        for r in (rows or []):
            features.append({
                "name": r["component"],
                "feature_count": r["feature_count"],
                "usage_count": r["usage_count"],
            })

        return {"features": features}

    def get_dashboard(self) -> dict[str, Any]:
        """Get a complete analytics dashboard snapshot."""
        usage = self.get_usage_stats()
        perf = self.get_performance_metrics()
        adoption = self.get_feature_adoption()

        # Health score (0-100)
        health = 100
        if perf["process"]["memory_mb"] > 500:
            health -= 10
        if perf["process"]["cpu_percent"] > 80:
            health -= 15
        if perf["system"]["memory_percent"] > 90:
            health -= 20

        return {
            "version": "0.9.0",
            "health_score": max(0, health),
            "usage": usage,
            "performance": perf,
            "adoption": adoption,
            "timestamp": time.time(),
        }

    def clear_old_events(self, days: int = 30) -> int:
        """Delete events older than N days. Returns count deleted."""
        cutoff = time.time() - (days * 86400)
        rows = self._run_async(
            db_execute(
                "SELECT COUNT(*) as count FROM analytics_events WHERE timestamp < ?",
                (cutoff,),
                fetch="all",
            )
        )
        count = rows[0]["count"] if rows else 0
        if count > 0:
            async def _delete():
                await db_execute("DELETE FROM analytics_events WHERE timestamp < ?", (cutoff,))
            self._run_async(_delete())
        return count

    def _run_async(self, coro):
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result(timeout=5)
        except RuntimeError:
            return asyncio.run(coro)
