"""Auto-update system for NEXORA.

Checks for new versions, downloads updates, and manages the update lifecycle.
Updates are applied via the packaging/restart mechanism.
"""
from __future__ import annotations

import json
import time
from typing import Any
from pathlib import Path

from loguru import logger

from .db import execute as db_execute

# Current version
CURRENT_VERSION = "0.9.0"
CURRENT_BUILD = 1

# Update repository URL (GitHub releases)
UPDATE_REPO = "Faheemkhalil/nexora"
UPDATE_CHECK_INTERVAL = 3600  # 1 hour


def _ensure_table() -> None:
    """Create update tracking tables."""
    import asyncio

    async def _create():
        await db_execute("""
            CREATE TABLE IF NOT EXISTS update_history (
                id TEXT PRIMARY KEY,
                from_version TEXT NOT NULL,
                to_version TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at REAL,
                completed_at REAL,
                error TEXT DEFAULT ''
            )
        """)
        await db_execute("""
            CREATE TABLE IF NOT EXISTS update_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pool.submit(asyncio.run, _create()).result(timeout=5)
    except RuntimeError:
        asyncio.run(_create())


class UpdateManager:
    """Manages version checking and update lifecycle."""

    def __init__(self) -> None:
        _ensure_table()

    def get_current_version(self) -> dict[str, Any]:
        """Return the current version information."""
        return {
            "version": CURRENT_VERSION,
            "build": CURRENT_BUILD,
            "update_url": f"https://github.com/{UPDATE_REPO}/releases",
            "check_interval": UPDATE_CHECK_INTERVAL,
        }

    async def check_for_updates(self) -> dict[str, Any]:
        """Check if a new version is available.

        In production this would query GitHub releases API.
        For now, simulates the check.
        """
        import aiohttp

        try:
            url = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        latest_tag = data.get("tag_name", "").lstrip("v")
                        return {
                            "available": latest_tag != CURRENT_VERSION,
                            "latest_version": latest_tag or CURRENT_VERSION,
                            "current_version": CURRENT_VERSION,
                            "release_notes": data.get("body", "")[:500],
                            "download_url": data.get("html_url", ""),
                            "published_at": data.get("published_at", ""),
                        }
        except Exception as e:
            logger.debug(f"Update check failed (non-fatal): {e}")

        # Fallback — no update available
        return {
            "available": False,
            "latest_version": CURRENT_VERSION,
            "current_version": CURRENT_VERSION,
            "release_notes": "",
            "download_url": "",
            "published_at": "",
        }

    def record_update_attempt(self, to_version: str) -> str:
        """Record an update attempt."""
        import uuid
        update_id = f"upd_{uuid.uuid4().hex[:8]}"
        now = time.time()

        async def _insert():
            await db_execute(
                """INSERT INTO update_history (id, from_version, to_version, status, started_at)
                   VALUES (?, ?, ?, 'in_progress', ?)""",
                (update_id, CURRENT_VERSION, to_version, now),
            )

        self._run_async(_insert())
        return update_id

    def complete_update(self, update_id: str, success: bool, error: str = "") -> None:
        """Mark an update as completed or failed."""
        status = "completed" if success else "failed"

        async def _update():
            await db_execute(
                "UPDATE update_history SET status = ?, completed_at = ?, error = ? WHERE id = ?",
                (status, time.time(), error, update_id),
            )

        self._run_async(_update())

    def get_update_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent update history."""
        rows = self._run_async(
            db_execute(
                "SELECT * FROM update_history ORDER BY started_at DESC LIMIT ?",
                (limit,),
                fetch="all",
            )
        )
        return [
            {
                "id": r["id"],
                "from_version": r["from_version"],
                "to_version": r["to_version"],
                "status": r["status"],
                "started_at": r["started_at"],
                "completed_at": r["completed_at"],
                "error": r["error"],
            }
            for r in (rows or [])
        ]

    def get_auto_update_setting(self) -> bool:
        """Check if auto-update is enabled."""
        rows = self._run_async(
            db_execute(
                "SELECT value FROM update_settings WHERE key = 'auto_update'",
                fetch="all",
            )
        )
        if rows:
            return rows[0]["value"] == "true"
        return True  # default enabled

    def set_auto_update(self, enabled: bool) -> None:
        """Enable or disable auto-updates."""
        async def _upsert():
            await db_execute(
                "INSERT OR REPLACE INTO update_settings (key, value) VALUES ('auto_update', ?)",
                ("true" if enabled else "false",),
            )
        self._run_async(_upsert())

    def _run_async(self, coro):
        """Run an async coroutine from sync context."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result(timeout=5)
        except RuntimeError:
            return asyncio.run(coro)
