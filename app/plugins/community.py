"""Community features for the NEXORA plugin ecosystem.

Provides rating, favorites, collections, and plugin sharing capabilities.
All data is stored locally and can be synced with a remote registry.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from loguru import logger

from ..core.db import execute as db_execute


def _ensure_table() -> None:
    """Create community tables if needed."""
    import asyncio

    async def _create():
        await db_execute("""
            CREATE TABLE IF NOT EXISTS community_favorites (
                id TEXT PRIMARY KEY,
                plugin_name TEXT NOT NULL UNIQUE,
                added_at REAL
            )
        """)
        await db_execute("""
            CREATE TABLE IF NOT EXISTS community_ratings (
                id TEXT PRIMARY KEY,
                plugin_name TEXT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT DEFAULT '',
                created_at REAL
            )
        """)
        await db_execute("""
            CREATE TABLE IF NOT EXISTS community_collections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                plugins TEXT DEFAULT '[]',
                created_at REAL,
                updated_at REAL
            )
        """)

    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pool.submit(asyncio.run, _create()).result(timeout=5)
    except RuntimeError:
        asyncio.run(_create())


class CommunityManager:
    """Manages community features: favorites, ratings, and collections."""

    def __init__(self) -> None:
        _ensure_table()

    # ── Favorites ────────────────────────────────────────────────────────

    def add_favorite(self, plugin_name: str) -> dict[str, Any]:
        """Add a plugin to favorites."""
        fav_id = f"fav_{uuid.uuid4().hex[:8]}"

        async def _insert():
            await db_execute(
                "INSERT OR REPLACE INTO community_favorites (id, plugin_name, added_at) VALUES (?, ?, ?)",
                (fav_id, plugin_name, time.time()),
            )

        self._run_async(_insert())
        return {"id": fav_id, "plugin": plugin_name, "added_at": time.time()}

    def remove_favorite(self, plugin_name: str) -> bool:
        """Remove a plugin from favorites."""
        self._run_async(
            db_execute("DELETE FROM community_favorites WHERE plugin_name = ?", (plugin_name,))
        )
        return True

    def get_favorites(self) -> list[dict[str, Any]]:
        """Get all favorite plugins."""
        rows = self._run_async(
            db_execute("SELECT * FROM community_favorites ORDER BY added_at DESC", fetch="all")
        )
        return [{"id": r["id"], "plugin": r["plugin_name"], "added_at": r["added_at"]} for r in (rows or [])]

    def is_favorite(self, plugin_name: str) -> bool:
        """Check if a plugin is a favorite."""
        rows = self._run_async(
            db_execute("SELECT 1 FROM community_favorites WHERE plugin_name = ?", (plugin_name,), fetch="all")
        )
        return bool(rows)

    # ── Ratings ──────────────────────────────────────────────────────────

    def rate_plugin(self, plugin_name: str, rating: int, comment: str = "") -> dict[str, Any]:
        """Rate a plugin (1-5 stars)."""
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        rate_id = f"rat_{uuid.uuid4().hex[:8]}"

        async def _insert():
            await db_execute(
                """INSERT INTO community_ratings (id, plugin_name, rating, comment, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (rate_id, plugin_name, rating, comment, time.time()),
            )

        self._run_async(_insert())
        return {"id": rate_id, "plugin": plugin_name, "rating": rating, "comment": comment}

    def get_ratings(self, plugin_name: str) -> list[dict[str, Any]]:
        """Get all ratings for a plugin."""
        rows = self._run_async(
            db_execute(
                "SELECT * FROM community_ratings WHERE plugin_name = ? ORDER BY created_at DESC",
                (plugin_name,),
                fetch="all",
            )
        )
        return [
            {"id": r["id"], "rating": r["rating"], "comment": r["comment"], "created_at": r["created_at"]}
            for r in (rows or [])
        ]

    def get_average_rating(self, plugin_name: str) -> float:
        """Get average rating for a plugin."""
        rows = self._run_async(
            db_execute(
                "SELECT AVG(rating) as avg_rating, COUNT(*) as count FROM community_ratings WHERE plugin_name = ?",
                (plugin_name,),
                fetch="all",
            )
        )
        if rows and rows[0] and rows[0]["avg_rating"] is not None:
            return round(float(rows[0]["avg_rating"]), 1)
        return 0.0

    # ── Collections ──────────────────────────────────────────────────────

    def create_collection(self, name: str, description: str = "",
                          plugins: list[str] | None = None) -> dict[str, Any]:
        """Create a named collection of plugins."""
        col_id = f"col_{uuid.uuid4().hex[:8]}"
        now = time.time()

        async def _insert():
            await db_execute(
                """INSERT INTO community_collections (id, name, description, plugins, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (col_id, name, description, json.dumps(plugins or []), now, now),
            )

        self._run_async(_insert())
        return {"id": col_id, "name": name, "description": description, "plugins": plugins or []}

    def update_collection(self, collection_id: str, name: str | None = None,
                          description: str | None = None, plugins: list[str] | None = None) -> bool:
        """Update a collection."""
        updates = []
        params: list[Any] = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if plugins is not None:
            updates.append("plugins = ?")
            params.append(json.dumps(plugins))
        if not updates:
            return False
        updates.append("updated_at = ?")
        params.append(time.time())
        params.append(collection_id)

        self._run_async(
            db_execute(f"UPDATE community_collections SET {', '.join(updates)} WHERE id = ?", tuple(params))
        )
        return True

    def delete_collection(self, collection_id: str) -> bool:
        """Delete a collection."""
        self._run_async(
            db_execute("DELETE FROM community_collections WHERE id = ?", (collection_id,))
        )
        return True

    def get_collections(self) -> list[dict[str, Any]]:
        """Get all collections."""
        rows = self._run_async(
            db_execute("SELECT * FROM community_collections ORDER BY created_at DESC", fetch="all")
        )
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "plugins": json.loads(r["plugins"] or "[]"),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in (rows or [])
        ]

    def get_collection(self, collection_id: str) -> dict[str, Any] | None:
        """Get a specific collection."""
        rows = self._run_async(
            db_execute("SELECT * FROM community_collections WHERE id = ?", (collection_id,), fetch="all")
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "plugins": json.loads(r["plugins"] or "[]"),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }

    # ── Helper ───────────────────────────────────────────────────────────

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
