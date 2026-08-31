"""Extension marketplace client.

Provides a curated catalog of NEXORA plugins that can be browsed,
searched, and installed. The catalog is stored locally and can be
synced with a remote registry (when available).
"""
from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger

from ..core.db import execute as db_execute


# ---------------------------------------------------------------------------
# Built-in catalog (shipped with NEXORA)
# ---------------------------------------------------------------------------
BUILTIN_CATALOG: list[dict[str, Any]] = [
    {
        "name": "nmap-scanner",
        "version": "1.0.0",
        "description": "Network port scanner integration using nmap",
        "author": "NEXORA Team",
        "category": "security",
        "permissions": ["terminal.execute"],
        "icon": "🔍",
        "downloads": 1250,
        "rating": 4.7,
        "featured": True,
        "tags": ["security", "network", "scanning"],
    },
    {
        "name": "python-linter",
        "version": "1.2.0",
        "description": "Python code linting and formatting with ruff and black",
        "author": "NEXORA Team",
        "category": "coding",
        "permissions": ["terminal.execute"],
        "icon": "🐍",
        "downloads": 3400,
        "rating": 4.8,
        "featured": True,
        "tags": ["python", "linting", "formatting"],
    },
    {
        "name": "docker-manager",
        "version": "1.1.0",
        "description": "Docker container and image management",
        "author": "Community",
        "category": "system",
        "permissions": ["terminal.execute", "system.info"],
        "icon": "🐳",
        "downloads": 890,
        "rating": 4.5,
        "featured": False,
        "tags": ["docker", "containers", "devops"],
    },
    {
        "name": "web-scraper",
        "version": "2.0.0",
        "description": "Advanced web scraping with CSS selectors and data extraction",
        "author": "Community",
        "category": "internet",
        "permissions": ["internet.fetch"],
        "icon": "🕷️",
        "downloads": 2100,
        "rating": 4.3,
        "featured": True,
        "tags": ["web", "scraping", "data"],
    },
    {
        "name": "ssh-manager",
        "version": "1.0.0",
        "description": "SSH connection manager with key management",
        "author": "NEXORA Team",
        "category": "system",
        "permissions": ["terminal.execute"],
        "icon": "🔐",
        "downloads": 1600,
        "rating": 4.6,
        "featured": False,
        "tags": ["ssh", "remote", "connections"],
    },
    {
        "name": "api-tester",
        "version": "1.3.0",
        "description": "REST and GraphQL API testing tool",
        "author": "Community",
        "category": "coding",
        "permissions": ["internet.fetch"],
        "icon": "🧪",
        "downloads": 950,
        "rating": 4.4,
        "featured": False,
        "tags": ["api", "testing", "rest", "graphql"],
    },
    {
        "name": "git-flow",
        "version": "1.0.0",
        "description": "GitFlow workflow automation for branch management",
        "author": "NEXORA Team",
        "category": "coding",
        "permissions": ["terminal.execute"],
        "icon": "🌿",
        "downloads": 780,
        "rating": 4.2,
        "featured": False,
        "tags": ["git", "workflow", "branching"],
    },
    {
        "name": "password-audit",
        "version": "1.1.0",
        "description": "Password strength auditor and breach checker",
        "author": "NEXORA Team",
        "category": "security",
        "permissions": ["internet.fetch"],
        "icon": "🔑",
        "downloads": 1400,
        "rating": 4.8,
        "featured": True,
        "tags": ["security", "passwords", "audit"],
    },
    {
        "name": "database-explorer",
        "version": "1.0.0",
        "description": "SQLite and PostgreSQL database explorer",
        "author": "Community",
        "category": "coding",
        "permissions": ["file.read", "terminal.execute"],
        "icon": "🗄️",
        "downloads": 650,
        "rating": 4.1,
        "featured": False,
        "tags": ["database", "sql", "explorer"],
    },
    {
        "name": "voice-commands",
        "version": "1.2.0",
        "description": "Extended voice command library with custom wake words",
        "author": "NEXORA Team",
        "category": "voice",
        "permissions": ["voice.speak"],
        "icon": "🎤",
        "downloads": 520,
        "rating": 4.0,
        "featured": False,
        "tags": ["voice", "commands", "wake-word"],
    },
]


def _ensure_table() -> None:
    """Create marketplace tables if needed."""
    import asyncio

    async def _create():
        await db_execute("""
            CREATE TABLE IF NOT EXISTS marketplace_downloads (
                id TEXT PRIMARY KEY,
                plugin_name TEXT NOT NULL,
                version TEXT NOT NULL,
                downloaded_at REAL,
                rating REAL DEFAULT 0
            )
        """)

    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pool.submit(asyncio.run, _create()).result(timeout=5)
    except RuntimeError:
        asyncio.run(_create())


class MarketplaceClient:
    """Client for the NEXORA extension marketplace."""

    def __init__(self) -> None:
        _ensure_table()

    def search(self, query: str = "", category: str = "",
               tags: list[str] | None = None) -> list[dict[str, Any]]:
        """Search the catalog by name, description, or tags."""
        results = list(BUILTIN_CATALOG)

        if query:
            q = query.lower()
            results = [
                p for p in results
                if q in p["name"].lower()
                or q in p["description"].lower()
                or any(q in t.lower() for t in p.get("tags", []))
            ]

        if category:
            results = [p for p in results if p.get("category") == category]

        if tags:
            tag_set = {t.lower() for t in tags}
            results = [
                p for p in results
                if tag_set & {t.lower() for t in p.get("tags", [])}
            ]

        return results

    def get_featured(self) -> list[dict[str, Any]]:
        """Return featured plugins."""
        return [p for p in BUILTIN_CATALOG if p.get("featured")]

    def get_trending(self) -> list[dict[str, Any]]:
        """Return top plugins sorted by downloads."""
        return sorted(BUILTIN_CATALOG, key=lambda p: p.get("downloads", 0), reverse=True)[:10]

    def get_categories(self) -> list[dict[str, Any]]:
        """Return category summaries."""
        cats: dict[str, int] = {}
        for p in BUILTIN_CATALOG:
            cat = p.get("category", "other")
            cats[cat] = cats.get(cat, 0) + 1
        return [{"name": k, "count": v} for k, v in sorted(cats.items())]

    def get_plugin(self, name: str) -> dict[str, Any] | None:
        """Get a specific plugin by name."""
        for p in BUILTIN_CATALOG:
            if p["name"] == name:
                return dict(p)
        return None

    def get_reviews(self, name: str) -> list[dict[str, Any]]:
        """Get simulated reviews for a plugin."""
        plugin = self.get_plugin(name)
        if not plugin:
            return []
        # Return synthetic reviews based on rating
        rating = plugin.get("rating", 4.0)
        return [
            {
                "author": "user_a",
                "rating": min(5, int(rating + 1)),
                "comment": f"Great {name} plugin, works well!",
                "date": "2026-08-15",
            },
            {
                "author": "user_b",
                "rating": max(1, int(rating - 0.5)),
                "comment": f"Solid {name} plugin with minor issues.",
                "date": "2026-08-10",
            },
        ]

    def record_download(self, name: str, version: str) -> dict[str, Any]:
        """Record a plugin download."""
        import uuid
        download_id = f"dl_{uuid.uuid4().hex[:8]}"
        now = time.time()

        async def _insert():
            await db_execute(
                "INSERT INTO marketplace_downloads (id, plugin_name, version, downloaded_at) VALUES (?, ?, ?, ?)",
                (download_id, name, version, now),
            )

        try:
            loop = __import__("asyncio").get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(__import__("asyncio").run, _insert()).result(timeout=5)
        except RuntimeError:
            __import__("asyncio").run(_insert())

        return {"id": download_id, "plugin": name, "version": version, "downloaded_at": now}

    def get_stats(self) -> dict[str, Any]:
        """Get marketplace statistics."""
        total = len(BUILTIN_CATALOG)
        total_downloads = sum(p.get("downloads", 0) for p in BUILTIN_CATALOG)
        categories = len(set(p.get("category") for p in BUILTIN_CATALOG))
        return {
            "total_plugins": total,
            "total_downloads": total_downloads,
            "categories": categories,
            "featured": sum(1 for p in BUILTIN_CATALOG if p.get("featured")),
        }
