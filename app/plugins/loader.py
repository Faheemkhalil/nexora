"""Plugin loader and lifecycle manager.

Plugins are Python packages under the plugins/ directory with a manifest.json.
Each plugin can register tools, IPC handlers, and UI components.
Plugins run in a restricted sandbox with explicit permission grants.
"""
from __future__ import annotations

import json
import importlib
import importlib.util
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from ..core.db import execute as db_execute


# ---------------------------------------------------------------------------
# Plugin manifest schema (checked at load time)
# ---------------------------------------------------------------------------
REQUIRED_MANIFEST_KEYS = {"name", "version", "description", "author"}
OPTIONAL_MANIFEST_KEYS = {"permissions", "dependencies", "entry", "icon", "category", "enabled"}

PLUGIN_DIR = Path(__file__).resolve().parent.parent.parent / "plugins"


def _ensure_table() -> None:
    """Create the installed_plugins table if it does not exist."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    async def _create():
        await db_execute("""
            CREATE TABLE IF NOT EXISTS installed_plugins (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                description TEXT DEFAULT '',
                author TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                permissions TEXT DEFAULT '[]',
                installed_at REAL,
                updated_at REAL,
                config TEXT DEFAULT '{}'
            )
        """)

    if loop and loop.is_running():
        # We're inside an async context — schedule and forget
        import asyncio as _aio
        _aio.ensure_future(_create())
    else:
        if loop:
            loop.run_until_complete(_create())
        else:
            import asyncio as _aio
            _aio.run(_create())


# ---------------------------------------------------------------------------
# PluginManager
# ---------------------------------------------------------------------------
class PluginManager:
    """Manages plugin discovery, loading, and lifecycle."""

    def __init__(self) -> None:
        self._plugins: dict[str, dict[str, Any]] = {}  # name -> plugin info
        self._loaded: dict[str, Any] = {}  # name -> loaded module
        self._tools: dict[str, list] = {}  # name -> registered tools
        PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
        _ensure_table()

    # ── Discovery ────────────────────────────────────────────────────────

    def discover(self) -> list[dict[str, Any]]:
        """Scan the plugins directory and return manifest info."""
        plugins = []
        if not PLUGIN_DIR.exists():
            return plugins

        for child in PLUGIN_DIR.iterdir():
            if child.is_dir() and not child.name.startswith("_"):
                manifest_path = child / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path) as f:
                            manifest = json.load(f)
                        manifest["_path"] = str(child)
                        plugins.append(manifest)
                    except Exception as e:
                        logger.warning(f"Failed to load manifest from {child.name}: {e}")
        return plugins

    def get_installed(self) -> list[dict[str, Any]]:
        """Return list of installed plugins from the database."""
        import asyncio

        async def _query():
            return await db_execute(
                "SELECT * FROM installed_plugins ORDER BY installed_at DESC",
                fetch="all",
            )

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _query())
                rows = future.result(timeout=5)
        except RuntimeError:
            rows = asyncio.run(_query())

        results = []
        for row in (rows or []):
            results.append({
                "id": row["id"],
                "name": row["name"],
                "version": row["version"],
                "description": row["description"],
                "author": row["author"],
                "enabled": bool(row["enabled"]),
                "permissions": json.loads(row["permissions"] or "[]"),
                "installed_at": row["installed_at"],
                "updated_at": row["updated_at"],
                "config": json.loads(row["config"] or "{}"),
            })
        return results

    # ── Install / Uninstall ──────────────────────────────────────────────

    def install(self, name: str, version: str = "latest",
                manifest: dict[str, Any] | None = None) -> dict[str, Any]:
        """Install a plugin from manifest or create a placeholder entry."""
        now = time.time()
        plugin_id = f"plg_{uuid.uuid4().hex[:8]}"

        if manifest is None:
            manifest = {
                "name": name,
                "version": version,
                "description": "",
                "author": "",
                "permissions": [],
            }

        import asyncio

        async def _insert():
            await db_execute(
                """INSERT OR REPLACE INTO installed_plugins
                   (id, name, version, description, author, enabled, permissions, installed_at, updated_at, config)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, '{}')""",
                (
                    plugin_id,
                    manifest.get("name", name),
                    manifest.get("version", version),
                    manifest.get("description", ""),
                    manifest.get("author", ""),
                    json.dumps(manifest.get("permissions", [])),
                    now,
                    now,
                ),
            )

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _insert()).result(timeout=5)
        except RuntimeError:
            asyncio.run(_insert())

        logger.info(f"Plugin installed: {name} v{version} ({plugin_id})")
        return {
            "id": plugin_id,
            "name": name,
            "version": version,
            "enabled": True,
            "installed_at": now,
        }

    def uninstall(self, plugin_id: str) -> bool:
        """Remove a plugin from the database."""
        import asyncio

        async def _delete():
            await db_execute(
                "DELETE FROM installed_plugins WHERE id = ?",
                (plugin_id,),
            )

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _delete()).result(timeout=5)
        except RuntimeError:
            asyncio.run(_delete())

        # Unload if loaded
        for name, info in list(self._plugins.items()):
            if info.get("id") == plugin_id:
                self._loaded.pop(name, None)
                self._plugins.pop(name, None)
                self._tools.pop(name, None)
                break

        logger.info(f"Plugin uninstalled: {plugin_id}")
        return True

    def toggle(self, plugin_id: str, enabled: bool) -> bool:
        """Enable or disable a plugin."""
        import asyncio

        async def _update():
            await db_execute(
                "UPDATE installed_plugins SET enabled = ?, updated_at = ? WHERE id = ?",
                (1 if enabled else 0, time.time(), plugin_id),
            )

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _update()).result(timeout=5)
        except RuntimeError:
            asyncio.run(_update())

        logger.info(f"Plugin {plugin_id}: enabled={enabled}")
        return True

    # ── Plugin API ───────────────────────────────────────────────────────

    def list_available(self) -> list[dict[str, Any]]:
        """List all discoverable plugins (from filesystem)."""
        return self.discover()

    def get_plugin_info(self, name: str) -> dict[str, Any] | None:
        """Get info about a specific plugin."""
        for p in self.discover():
            if p.get("name") == name:
                return p
        return None

    def validate_manifest(self, manifest: dict[str, Any]) -> tuple[bool, str]:
        """Validate a plugin manifest. Returns (valid, error_message)."""
        missing = REQUIRED_MANIFEST_KEYS - set(manifest.keys())
        if missing:
            return False, f"Missing required keys: {', '.join(sorted(missing))}"
        if not isinstance(manifest.get("version"), str):
            return False, "Version must be a string"
        return True, ""
