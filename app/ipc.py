"""IPC layer — aiohttp HTTP API + WebSocket server.

The frontend connects via WebSocket to exchange messages with the backend.
All sensitive operations require explicit permission checks.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from aiohttp import web, WSMsgType

from loguru import logger

from .core.config import settings
from .core.db import execute
from .core.diagnostics import run_all_diagnostics
from .core.errors import NexoraError, AuthenticationError, ProviderError, VoiceError, ToolError
from .providers import manager
from .voice import VoiceManager, VoiceState
from .tools import registry
from .tools.permissions import permissions

_UI_DIR = Path(__file__).resolve().parent.parent / "ui"
_UI_DIST_DIR = _UI_DIR / "dist"


class IPCServer:
    """Manages the HTTP API and WebSocket IPC server."""

    def __init__(self) -> None:
        self._app = web.Application()
        self._app.router.add_get("/ws", self._websocket_handler)
        self._app.router.add_post("/api/chat", self._http_chat)
        self._app.router.add_get("/api/providers", self._http_list_providers)
        self._app.router.add_get("/api/diagnostics", self._http_diagnostics)
        self._app.router.add_get("/api/conversations", self._http_list_conversations)
        self._app.router.add_post("/api/conversations", self._http_create_conversation)
        self._app.router.add_get("/healthz", self._health)

        # Serve static frontend files from ui/dist/ (if built) or ui/ as /webui/
        ui_root = _UI_DIST_DIR if _UI_DIST_DIR.exists() else _UI_DIR
        if ui_root.exists():
            # Serve static assets and index.html
            self._app.router.add_static("/webui/assets/", ui_root / "assets", follow_symlinks=True)
            async def _serve_index(request):
                return web.FileResponse(ui_root / "index.html")
            self._app.router.add_get("/webui/", _serve_index)
            self._app.router.add_get("/webui/index.html", _serve_index)
            logger.debug(f"Serving UI from {ui_root}")
        else:
            logger.warning(f"UI directory not found at {_UI_DIR}")

        self._ws_clients: set[web.WebSocketResponse] = set()
        self._handlers: dict[str, callable] = {
            "ping": self._handle_ping,
            "chat": self._handle_chat,
            "chat_stream": self._handle_chat_stream,
            "providers.list": self._handle_providers_list,
            "providers.add": self._handle_providers_add,
            "providers.remove": self._handle_providers_remove,
            "providers.test": self._handle_providers_test,
            "diagnostics": self._handle_diagnostics,
            "conversations.list": self._handle_conversations_list,
            "conversations.create": self._handle_conversations_create,
            "conversations.get": self._handle_conversations_get,
            "settings.get": self._handle_settings_get,
            "settings.set": self._handle_settings_set,
            "voice.state": self._handle_voice_state,
            "voice.listen": self._handle_voice_listen,
            "voice.speak": self._handle_voice_speak,
            "voice.stop": self._handle_voice_stop,
            "voice.devices": self._handle_voice_devices,
            "voice.configure": self._handle_voice_configure,
            "tools.list": self._handle_tools_list,
            "tools.execute": self._handle_tools_execute,
            "tools.confirm": self._handle_tools_confirm,
            "tools.cancel": self._handle_tools_cancel,
            "tools.sessions": self._handle_tools_sessions,
            "tools.audit": self._handle_tools_audit,
            "tools.emergency_stop": self._handle_tools_emergency_stop,
            "tools.emergency_reset": self._handle_tools_emergency_reset,
            # Coding handlers
            "coding.read_file": self._handle_coding_read_file,
            "coding.write_file": self._handle_coding_write_file,
            "coding.search": self._handle_coding_search,
            "coding.list_dir": self._handle_coding_list_dir,
            "coding.git.status": self._handle_coding_git_status,
            "coding.git.diff": self._handle_coding_git_diff,
            "coding.git.log": self._handle_coding_git_log,
            "coding.git.add": self._handle_coding_git_add,
            "coding.git.commit": self._handle_coding_git_commit,
            "coding.git.branch": self._handle_coding_git_branch,
            "coding.test.run": self._handle_coding_test_run,
            "coding.agent.explain": self._handle_coding_agent_explain,
            "coding.agent.generate": self._handle_coding_agent_generate,
            "coding.agent.refactor": self._handle_coding_agent_refactor,
            "coding.agent.find_bugs": self._handle_coding_agent_find_bugs,
            "coding.agent.create_tests": self._handle_coding_agent_create_tests,
            "coding.projects.list": self._handle_coding_projects_list,
            "coding.projects.open": self._handle_coding_projects_open,
            # Internet handlers
            "internet.search": self._handle_internet_search,
            "internet.fetch": self._handle_internet_fetch,
            "internet.fetch_json": self._handle_internet_fetch_json,
            "internet.docs": self._handle_internet_docs,
            "internet.open": self._handle_internet_open,
            # Security handlers
            "security.findings.create": self._handle_security_findings_create,
            "security.findings.list": self._handle_security_findings_list,
            "security.findings.update": self._handle_security_findings_update,
            "security.findings.delete": self._handle_security_findings_delete,
            "security.findings.summary": self._handle_security_findings_summary,
            "security.lab.create": self._handle_security_lab_create,
            "security.lab.status": self._handle_security_lab_status,
            "security.lab.start": self._handle_security_lab_start,
            "security.lab.stop": self._handle_security_lab_stop,
            "security.lab.delete": self._handle_security_lab_delete,
            "security.reports.generate": self._handle_security_reports_generate,
            "security.scope.check": self._handle_security_scope_check,
            "security.scope.add": self._handle_security_scope_add,
            "security.scope.list": self._handle_security_scope_list,
            "security.scope.delete": self._handle_security_scope_delete,
            # Memory handlers
            "memory.set": self._handle_memory_set,
            "memory.get": self._handle_memory_get,
            "memory.search": self._handle_memory_search,
            "memory.delete": self._handle_memory_delete,
            "memory.clear": self._handle_memory_clear,
            "memory.scopes": self._handle_memory_scopes,
            # Local AI
            "local_ai.detect": self._handle_local_ai_detect,
            # Auto-update
            "update.version": self._handle_update_version,
            "update.check": self._handle_update_check,
            "update.history": self._handle_update_history,
            "update.auto_update": self._handle_update_auto_toggle,
            # Crash reporting
            "crash.reports": self._handle_crash_reports,
            "crash.stats": self._handle_crash_stats,
            "crash.capture": self._handle_crash_capture,
            "crash.clear": self._handle_crash_clear,
            # Analytics
            "analytics.track": self._handle_analytics_track,
            "analytics.usage": self._handle_analytics_usage,
            "analytics.performance": self._handle_analytics_performance,
            "analytics.adoption": self._handle_analytics_adoption,
            "analytics.dashboard": self._handle_analytics_dashboard,
            # Plugin system
            "plugins.list": self._handle_plugins_list,
            "plugins.installed": self._handle_plugins_installed,
            "plugins.install": self._handle_plugins_install,
            "plugins.uninstall": self._handle_plugins_uninstall,
            "plugins.toggle": self._handle_plugins_toggle,
            # Marketplace
            "marketplace.search": self._handle_marketplace_search,
            "marketplace.featured": self._handle_marketplace_featured,
            "marketplace.trending": self._handle_marketplace_trending,
            "marketplace.categories": self._handle_marketplace_categories,
            "marketplace.stats": self._handle_marketplace_stats,
            "marketplace.reviews": self._handle_marketplace_reviews,
            # Community
            "community.favorites": self._handle_community_favorites,
            "community.favorite.add": self._handle_community_favorite_add,
            "community.favorite.remove": self._handle_community_favorite_remove,
            "community.rate": self._handle_community_rate,
            "community.ratings": self._handle_community_ratings,
            "community.collections": self._handle_community_collections,
            "community.collection.create": self._handle_community_collection_create,
            "community.collection.delete": self._handle_community_collection_delete,
            "community.collection.update": self._handle_community_collection_update,
            "shutdown": self._handle_shutdown,
        }
        self._shutdown_requested = False
        self._runner: web.AppRunner | None = None
        self._voice: VoiceManager | None = None

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def get_url(self) -> str:
        return f"ws://{settings.server.host}:{settings.server.port}/ws"

    async def start(self) -> None:
        """Start the HTTP/WebSocket server."""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(
            self._runner,
            host=settings.server.host,
            port=settings.server.port,
        )
        await site.start()

        # Initialize voice pipeline
        voice_cfg = settings.voice
        try:
            self._voice = VoiceManager(
                stt_engine=voice_cfg.stt_engine,
                tts_engine=voice_cfg.tts_engine,
                tts_voice=voice_cfg.tts_voice,
                language=voice_cfg.language,
                microphone_device=voice_cfg.microphone_device,
            )
            self._voice.on_state_change(self._on_voice_state_change)
            logger.info(f"Voice pipeline initialized (STT={voice_cfg.stt_engine}, TTS={voice_cfg.tts_engine})")
        except VoiceError as e:
            logger.warning(f"Voice pipeline init failed (non-fatal): {e}")
            self._voice = None

        # Register all tools
        from .tools.file_tools import register_file_tools
        from .tools.system_tools import register_system_tools
        from .tools.terminal_tools import register_terminal_tools
        from .tools.app_tools import register_app_tools
        register_file_tools(registry)
        register_system_tools(registry)
        register_terminal_tools(registry)
        register_app_tools(registry)

        # Register coding tools
        from .coding.code_editor import register_code_tools
        from .coding.git_ops import register_git_tools
        from .coding.test_runner import register_test_tools
        from .coding.ai_agent import register_ai_tools
        from .coding.project_manager import register_project_tools
        register_code_tools(registry)
        register_git_tools(registry)
        register_test_tools(registry)
        register_ai_tools(registry)
        register_project_tools(registry)

        # Register internet tools
        from .internet.search import WebSearchTool
        from .internet.fetch import register_fetch_tools
        from .internet.docs import register_docs_tools
        from .internet.browser import register_browser_tools
        registry.register(WebSearchTool())
        register_fetch_tools(registry)
        register_docs_tools(registry)
        register_browser_tools(registry)

        # Register security tools
        from .security.findings import register_finding_tools
        from .security.lab import register_lab_tools
        from .security.reports import register_report_tools
        from .security.scope import register_scope_tools
        register_finding_tools(registry)
        register_lab_tools(registry)
        register_report_tools(registry)
        register_scope_tools(registry)

        # Register memory tools
        from .core.memory import register_memory_tools
        register_memory_tools(registry)
        logger.info(f"Tools registered: {len(registry.list_tools())} tools in {len(registry.list_categories())} categories")

        logger.info(
            f"IPC server started on {settings.server.host}:{settings.server.port}"
        )

    async def stop(self) -> None:
        """Stop the server and close all connections."""
        self._shutdown_requested = True
        for ws in list(self._ws_clients):
            await ws.close()
        self._ws_clients.clear()
        if self._voice:
            await self._voice.close()
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        logger.info("IPC server stopped.")

    # --- Voice state broadcast ---

    def _on_voice_state_change(self, state: VoiceState) -> None:
        """Broadcast voice state changes to all connected clients."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._send_event("voice_state", {"state": state.value}))
        except Exception:
            pass

    # --- Voice handlers ---

    async def _handle_voice_state(self, params: dict) -> dict:
        if not self._voice:
            return {"state": "error", "available": {"microphone": False, "stt": False, "tts": False, "pipeline": False}}
        return {
            "state": self._voice.state.value,
            "available": self._voice.available,
        }

    async def _handle_voice_listen(self, params: dict) -> dict:
        if not self._voice:
            raise VoiceError("Voice pipeline not available.")
        duration = params.get("duration", 5.0)
        text = await self._voice.start_listening(duration)
        return {"transcript": text}

    async def _handle_voice_speak(self, params: dict) -> dict:
        if not self._voice:
            raise VoiceError("Voice pipeline not available.")
        text = params.get("text", "")
        if not text:
            raise VoiceError("No text provided for speech synthesis.")
        audio = await self._voice.speak(text)
        return {"ok": True, "audio_size": len(audio)}

    async def _handle_voice_stop(self, params: dict) -> dict:
        if self._voice:
            from .voice import VoiceState
            self._voice._set_state(VoiceState.IDLE)
        return {"ok": True}

    async def _handle_voice_devices(self, params: dict) -> list:
        if not self._voice:
            return []
        return self._voice.list_devices()

    async def _handle_voice_configure(self, params: dict) -> dict:
        if not self._voice:
            raise VoiceError("Voice pipeline not available.")
        await self._voice.reconfigure(
            stt_engine=params.get("stt_engine"),
            tts_engine=params.get("tts_engine"),
            tts_voice=params.get("tts_voice"),
            language=params.get("language"),
            microphone_device=params.get("microphone_device"),
        )
        return {"ok": True, "available": self._voice.available}

    # --- Tool handlers ---

    async def _handle_tools_list(self, params: dict) -> list:
        category = params.get("category")
        return [s.to_dict() for s in registry.list_tools(category)]

    async def _handle_tools_execute(self, params: dict) -> dict:
        name = params.get("name")
        tool_inputs = params.get("inputs", {})
        confirmed = params.get("confirmed", False)

        if not name:
            raise ToolError("Tool name is required.")

        result = await registry.execute(name, tool_inputs, confirmed=confirmed)

        if result.error == "confirmation_required":
            return {
                "confirmation_required": True,
                "token": result.details,
                "tool": name,
                "inputs": tool_inputs,
            }

        return result.to_dict()

    async def _handle_tools_confirm(self, params: dict) -> dict:
        token = params.get("token")
        if not token:
            raise ToolError("Confirmation token required.")
        result = await registry.confirm_and_execute(token)
        return result.to_dict()

    async def _handle_tools_cancel(self, params: dict) -> dict:
        token = params.get("token")
        if token:
            await registry.cancel_confirmation(token)
        # Also cancel terminal sessions
        session_id = params.get("session_id")
        if session_id:
            from .tools.terminal_tools import ExecuteCommandTool
            tool = ExecuteCommandTool()
            await tool.cancel(session_id)
        return {"ok": True}

    async def _handle_tools_sessions(self, params: dict) -> dict:
        sessions = permissions.get_active_tasks()
        return {"sessions": sessions, "emergency_stop": permissions.is_emergency_stopped}

    async def _handle_tools_audit(self, params: dict) -> list:
        limit = params.get("limit", 50)
        return await permissions.get_audit_logs(limit)

    async def _handle_tools_emergency_stop(self, params: dict) -> dict:
        permissions.emergency_stop()
        return {"emergency_stop": True}

    async def _handle_tools_emergency_reset(self, params: dict) -> dict:
        permissions.reset_emergency_stop()
        return {"emergency_stop": False}

    # --- Coding handlers ---

    async def _handle_coding_read_file(self, params: dict) -> dict:
        result = await registry.execute("coding.read_file", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_write_file(self, params: dict) -> dict:
        result = await registry.execute("coding.write_file", params, confirmed=params.get("confirmed", False))
        if result.error == "confirmation_required":
            return {"confirmation_required": True, "token": result.details, "tool": "coding.write_file"}
        return result.to_dict()

    async def _handle_coding_search(self, params: dict) -> dict:
        result = await registry.execute("coding.search", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_list_dir(self, params: dict) -> dict:
        result = await registry.execute("coding.list_dir", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_git_status(self, params: dict) -> dict:
        result = await registry.execute("coding.git.status", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_git_diff(self, params: dict) -> dict:
        result = await registry.execute("coding.git.diff", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_git_log(self, params: dict) -> dict:
        result = await registry.execute("coding.git.log", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_git_add(self, params: dict) -> dict:
        result = await registry.execute("coding.git.add", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_git_commit(self, params: dict) -> dict:
        result = await registry.execute("coding.git.commit", params, confirmed=params.get("confirmed", False))
        if result.error == "confirmation_required":
            return {"confirmation_required": True, "token": result.details, "tool": "coding.git.commit"}
        return result.to_dict()

    async def _handle_coding_git_branch(self, params: dict) -> dict:
        result = await registry.execute("coding.git.branch", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_test_run(self, params: dict) -> dict:
        result = await registry.execute("coding.test.run", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_agent_explain(self, params: dict) -> dict:
        result = await registry.execute("coding.agent.explain", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_agent_generate(self, params: dict) -> dict:
        result = await registry.execute("coding.agent.generate", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_agent_refactor(self, params: dict) -> dict:
        result = await registry.execute("coding.agent.refactor", params, confirmed=params.get("confirmed", False))
        if result.error == "confirmation_required":
            return {"confirmation_required": True, "token": result.details, "tool": "coding.agent.refactor"}
        return result.to_dict()

    async def _handle_coding_agent_find_bugs(self, params: dict) -> dict:
        result = await registry.execute("coding.agent.find_bugs", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_agent_create_tests(self, params: dict) -> dict:
        result = await registry.execute("coding.agent.create_tests", params, confirmed=True)
        return result.to_dict()

    async def _handle_coding_projects_list(self, params: dict) -> dict:
        result = await registry.execute("coding.projects.list", {}, confirmed=True)
        return result.to_dict()

    async def _handle_coding_projects_open(self, params: dict) -> dict:
        result = await registry.execute("coding.projects.open", params, confirmed=True)
        return result.to_dict()

    # --- Internet handlers ---

    async def _handle_internet_search(self, params: dict) -> dict:
        result = await registry.execute("internet.search", params, confirmed=True)
        return result.to_dict()

    async def _handle_internet_fetch(self, params: dict) -> dict:
        result = await registry.execute("internet.fetch", params, confirmed=True)
        return result.to_dict()

    async def _handle_internet_fetch_json(self, params: dict) -> dict:
        result = await registry.execute("internet.fetch_json", params, confirmed=True)
        return result.to_dict()

    async def _handle_internet_docs(self, params: dict) -> dict:
        result = await registry.execute("internet.docs", params, confirmed=True)
        return result.to_dict()

    async def _handle_internet_open(self, params: dict) -> dict:
        result = await registry.execute("internet.open", params, confirmed=True)
        return result.to_dict()

    # --- Security handlers ---

    async def _handle_security_findings_create(self, params: dict) -> dict:
        result = await registry.execute("security.findings.create", params, confirmed=True)
        return result.to_dict()

    async def _handle_security_findings_list(self, params: dict) -> dict:
        result = await registry.execute("security.findings.list", params, confirmed=True)
        return result.to_dict()

    async def _handle_security_findings_update(self, params: dict) -> dict:
        result = await registry.execute("security.findings.update", params, confirmed=True)
        return result.to_dict()

    async def _handle_security_findings_delete(self, params: dict) -> dict:
        result = await registry.execute("security.findings.delete", params, confirmed=params.get("confirmed", False))
        if result.error == "confirmation_required":
            return {"confirmation_required": True, "token": result.details, "tool": "security.findings.delete"}
        return result.to_dict()

    async def _handle_security_findings_summary(self, params: dict) -> dict:
        result = await registry.execute("security.findings.summary", {}, confirmed=True)
        return result.to_dict()

    async def _handle_security_lab_create(self, params: dict) -> dict:
        result = await registry.execute("security.lab.create", params, confirmed=params.get("confirmed", False))
        if result.error == "confirmation_required":
            return {"confirmation_required": True, "token": result.details, "tool": "security.lab.create"}
        return result.to_dict()

    async def _handle_security_lab_status(self, params: dict) -> dict:
        result = await registry.execute("security.lab.status", params, confirmed=True)
        return result.to_dict()

    async def _handle_security_lab_start(self, params: dict) -> dict:
        result = await registry.execute("security.lab.start", params, confirmed=params.get("confirmed", False))
        if result.error == "confirmation_required":
            return {"confirmation_required": True, "token": result.details, "tool": "security.lab.start"}
        return result.to_dict()

    async def _handle_security_lab_stop(self, params: dict) -> dict:
        result = await registry.execute("security.lab.stop", params, confirmed=params.get("confirmed", False))
        if result.error == "confirmation_required":
            return {"confirmation_required": True, "token": result.details, "tool": "security.lab.stop"}
        return result.to_dict()

    async def _handle_security_lab_delete(self, params: dict) -> dict:
        result = await registry.execute("security.lab.delete", params, confirmed=params.get("confirmed", False))
        if result.error == "confirmation_required":
            return {"confirmation_required": True, "token": result.details, "tool": "security.lab.delete"}
        return result.to_dict()

    async def _handle_security_reports_generate(self, params: dict) -> dict:
        result = await registry.execute("security.reports.generate", params, confirmed=True)
        return result.to_dict()

    async def _handle_security_scope_check(self, params: dict) -> dict:
        result = await registry.execute("security.scope.check", params, confirmed=True)
        return result.to_dict()

    async def _handle_security_scope_add(self, params: dict) -> dict:
        result = await registry.execute("security.scope.add", params, confirmed=params.get("confirmed", False))
        if result.error == "confirmation_required":
            return {"confirmation_required": True, "token": result.details, "tool": "security.scope.add"}
        return result.to_dict()

    async def _handle_security_scope_list(self, params: dict) -> dict:
        result = await registry.execute("security.scope.list", params, confirmed=True)
        return result.to_dict()

    async def _handle_security_scope_delete(self, params: dict) -> dict:
        result = await registry.execute("security.scope.delete", params, confirmed=params.get("confirmed", False))
        if result.error == "confirmation_required":
            return {"confirmation_required": True, "token": result.details, "tool": "security.scope.delete"}
        return result.to_dict()

    # --- Memory handlers ---

    async def _handle_memory_set(self, params: dict) -> dict:
        result = await registry.execute("memory.set", params, confirmed=True)
        return result.to_dict()

    async def _handle_memory_get(self, params: dict) -> dict:
        result = await registry.execute("memory.get", params, confirmed=True)
        return result.to_dict()

    async def _handle_memory_search(self, params: dict) -> dict:
        result = await registry.execute("memory.search", params, confirmed=True)
        return result.to_dict()

    async def _handle_memory_delete(self, params: dict) -> dict:
        result = await registry.execute("memory.delete", params, confirmed=True)
        return result.to_dict()

    async def _handle_memory_clear(self, params: dict) -> dict:
        result = await registry.execute("memory.clear", params, confirmed=params.get("confirmed", False))
        if result.error == "confirmation_required":
            return {"confirmation_required": True, "token": result.details, "tool": "memory.clear"}
        return result.to_dict()

    async def _handle_memory_scopes(self, params: dict) -> dict:
        result = await registry.execute("memory.scopes", {}, confirmed=True)
        return result.to_dict()

    # --- Local AI handlers ---

    async def _handle_local_ai_detect(self, params: dict) -> dict:
        from .core.local_ai import detect_local_ai
        info = await detect_local_ai()
        return {"available": info is not None, "info": info}

    # ── Update handlers ─────────────────────────────────────────────

    async def _handle_update_version(self, params: dict) -> dict:
        from .core.updater import UpdateManager
        um = UpdateManager()
        return um.get_current_version()

    async def _handle_update_check(self, params: dict) -> dict:
        from .core.updater import UpdateManager
        um = UpdateManager()
        return await um.check_for_updates()

    async def _handle_update_history(self, params: dict) -> dict:
        from .core.updater import UpdateManager
        um = UpdateManager()
        return {"history": um.get_update_history()}

    async def _handle_update_auto_toggle(self, params: dict) -> dict:
        from .core.updater import UpdateManager
        um = UpdateManager()
        enabled = params.get("enabled", True)
        um.set_auto_update(enabled)
        return {"auto_update": enabled}

    # ── Crash report handlers ───────────────────────────────────────

    async def _handle_crash_reports(self, params: dict) -> dict:
        from .core.crash_reporter import CrashReporter
        cr = CrashReporter()
        limit = params.get("limit", 50)
        component = params.get("component")
        return {"reports": cr.get_reports(limit, component)}

    async def _handle_crash_stats(self, params: dict) -> dict:
        from .core.crash_reporter import CrashReporter
        cr = CrashReporter()
        return cr.get_crash_stats()

    async def _handle_crash_capture(self, params: dict) -> dict:
        from .core.crash_reporter import CrashReporter
        cr = CrashReporter()
        error_type = params.get("error_type", "ManualReport")
        message = params.get("message", "User-reported issue")
        component = params.get("component", "unknown")
        report_id = cr.capture_exception(
            RuntimeError(message), component,
            context={"error_type": error_type}
        )
        return {"captured": True, "report_id": report_id}

    async def _handle_crash_clear(self, params: dict) -> dict:
        from .core.crash_reporter import CrashReporter
        cr = CrashReporter()
        count = cr.clear_all()
        return {"cleared": count}

    # ── Analytics handlers ───────────────────────────────────────────

    async def _handle_analytics_track(self, params: dict) -> dict:
        from .core.analytics import AnalyticsManager
        am = AnalyticsManager()
        event_type = params.get("event_type", "unknown")
        component = params.get("component", "")
        details = params.get("details")
        am.track_event(event_type, component, details)
        return {"tracked": True}

    async def _handle_analytics_usage(self, params: dict) -> dict:
        from .core.analytics import AnalyticsManager
        am = AnalyticsManager()
        return am.get_usage_stats()

    async def _handle_analytics_performance(self, params: dict) -> dict:
        from .core.analytics import AnalyticsManager
        am = AnalyticsManager()
        return am.get_performance_metrics()

    async def _handle_analytics_adoption(self, params: dict) -> dict:
        from .core.analytics import AnalyticsManager
        am = AnalyticsManager()
        return am.get_feature_adoption()

    async def _handle_analytics_dashboard(self, params: dict) -> dict:
        from .core.analytics import AnalyticsManager
        am = AnalyticsManager()
        return am.get_dashboard()

    # ── Plugin handlers ──────────────────────────────────────────────

    async def _handle_plugins_list(self, params: dict) -> dict:
        from .plugins.loader import PluginManager
        pm = PluginManager()
        return {"plugins": pm.list_available()}

    async def _handle_plugins_installed(self, params: dict) -> dict:
        from .plugins.loader import PluginManager
        pm = PluginManager()
        return {"plugins": pm.get_installed()}

    async def _handle_plugins_install(self, params: dict) -> dict:
        from .plugins.loader import PluginManager
        pm = PluginManager()
        name = params.get("name", "")
        version = params.get("version", "latest")
        manifest = params.get("manifest")
        result = pm.install(name, version, manifest)
        return {"installed": True, "plugin": result}

    async def _handle_plugins_uninstall(self, params: dict) -> dict:
        from .plugins.loader import PluginManager
        pm = PluginManager()
        plugin_id = params.get("id", "")
        pm.uninstall(plugin_id)
        return {"uninstalled": True}

    async def _handle_plugins_toggle(self, params: dict) -> dict:
        from .plugins.loader import PluginManager
        pm = PluginManager()
        plugin_id = params.get("id", "")
        enabled = params.get("enabled", True)
        pm.toggle(plugin_id, enabled)
        return {"toggled": True, "enabled": enabled}

    # ── Marketplace handlers ─────────────────────────────────────────

    async def _handle_marketplace_search(self, params: dict) -> dict:
        from .plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        query = params.get("query", "")
        category = params.get("category", "")
        tags = params.get("tags")
        return {"results": mc.search(query, category, tags)}

    async def _handle_marketplace_featured(self, params: dict) -> dict:
        from .plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        return {"featured": mc.get_featured()}

    async def _handle_marketplace_trending(self, params: dict) -> dict:
        from .plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        return {"trending": mc.get_trending()}

    async def _handle_marketplace_categories(self, params: dict) -> dict:
        from .plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        return {"categories": mc.get_categories()}

    async def _handle_marketplace_stats(self, params: dict) -> dict:
        from .plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        return mc.get_stats()

    async def _handle_marketplace_reviews(self, params: dict) -> dict:
        from .plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        name = params.get("name", "")
        return {"reviews": mc.get_reviews(name)}

    # ── Community handlers ───────────────────────────────────────────

    async def _handle_community_favorites(self, params: dict) -> dict:
        from .plugins.community import CommunityManager
        cm = CommunityManager()
        return {"favorites": cm.get_favorites()}

    async def _handle_community_favorite_add(self, params: dict) -> dict:
        from .plugins.community import CommunityManager
        cm = CommunityManager()
        name = params.get("name", "")
        result = cm.add_favorite(name)
        return {"added": True, "favorite": result}

    async def _handle_community_favorite_remove(self, params: dict) -> dict:
        from .plugins.community import CommunityManager
        cm = CommunityManager()
        name = params.get("name", "")
        cm.remove_favorite(name)
        return {"removed": True}

    async def _handle_community_rate(self, params: dict) -> dict:
        from .plugins.community import CommunityManager
        cm = CommunityManager()
        name = params.get("name", "")
        rating = params.get("rating", 5)
        comment = params.get("comment", "")
        result = cm.rate_plugin(name, rating, comment)
        return {"rated": True, "rating": result}

    async def _handle_community_ratings(self, params: dict) -> dict:
        from .plugins.community import CommunityManager
        cm = CommunityManager()
        name = params.get("name", "")
        return {"ratings": cm.get_ratings(name), "average": cm.get_average_rating(name)}

    async def _handle_community_collections(self, params: dict) -> dict:
        from .plugins.community import CommunityManager
        cm = CommunityManager()
        return {"collections": cm.get_collections()}

    async def _handle_community_collection_create(self, params: dict) -> dict:
        from .plugins.community import CommunityManager
        cm = CommunityManager()
        name = params.get("name", "")
        desc = params.get("description", "")
        plugins = params.get("plugins", [])
        result = cm.create_collection(name, desc, plugins)
        return {"created": True, "collection": result}

    async def _handle_community_collection_delete(self, params: dict) -> dict:
        from .plugins.community import CommunityManager
        cm = CommunityManager()
        col_id = params.get("id", "")
        cm.delete_collection(col_id)
        return {"deleted": True}

    async def _handle_community_collection_update(self, params: dict) -> dict:
        from .plugins.community import CommunityManager
        cm = CommunityManager()
        col_id = params.get("id", "")
        name = params.get("name")
        desc = params.get("description")
        plugins = params.get("plugins")
        cm.update_collection(col_id, name, desc, plugins)
        return {"updated": True}

    async def _websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections from the frontend."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.add(ws)
        logger.info(f"WebSocket client connected. Total: {len(self._ws_clients)}")

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_ws_message(ws, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        finally:
            self._ws_clients.discard(ws)
            await ws.close()
            logger.info(f"WebSocket client disconnected. Total: {len(self._ws_clients)}")

        return ws

    async def _handle_ws_message(self, ws: web.WebSocketResponse, raw: str) -> None:
        """Route a WebSocket message to the appropriate handler."""
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error(ws, "invalid_json", "Message is not valid JSON.")
            return

        request_id = message.get("id", str(uuid.uuid4()))
        method = message.get("method", "")
        params = message.get("params", {})

        handler = self._handlers.get(method)
        if handler is None:
            await self._send_error(ws, "method_not_found", f"Unknown method: {method}")
            return

        try:
            result = await handler(params)
            await self._send_response(ws, request_id, result)
        except NexoraError as e:
            await self._send_error(
                ws, "app_error", str(e), request_id=request_id,
                category=e.category, details=e.details,
            )
        except Exception as e:
            logger.exception(f"Unhandled error in handler '{method}': {e}")
            await self._send_error(
                ws, "internal_error", "An internal error occurred.",
                request_id=request_id, details=str(e),
            )

    async def _send_response(self, ws: web.WebSocketResponse, request_id: str, result: Any) -> None:
        await ws.send_str(json.dumps({
            "id": request_id,
            "type": "response",
            "result": result,
        }))

    async def _send_error(
        self, ws: web.WebSocketResponse, code: str, message: str,
        request_id: str | None = None, category: str | None = None,
        details: str | None = None,
    ) -> None:
        payload = {
            "type": "error",
            "code": code,
            "message": message,
        }
        if request_id:
            payload["id"] = request_id
        if category:
            payload["category"] = category
        if details:
            payload["details"] = details
        await ws.send_str(json.dumps(payload))

    async def _send_event(self, event: str, data: Any) -> None:
        """Broadcast an event to all connected clients."""
        payload = json.dumps({"type": "event", "event": event, "data": data})
        for ws in list(self._ws_clients):
            try:
                await ws.send_str(payload)
            except Exception:
                pass

    # --- Handler implementations ---

    async def _handle_ping(self, params: dict) -> dict:
        return {"pong": True, "timestamp": time.time()}

    async def _handle_chat(self, params: dict) -> dict:
        provider_id = params.get("provider_id")
        message = params.get("message", "")
        conversation_id = params.get("conversation_id")

        provider = await self._get_provider_or_default(provider_id)
        from .providers.base import ChatMessage

        messages = [ChatMessage(role="user", content=message)]
        content = ""

        async for resp in provider.chat(messages):
            if not resp.streaming:
                content = resp.content
                break

        # Create conversation if needed
        if not conversation_id:
            conv_id = str(uuid.uuid4())
            await execute(
                "INSERT INTO conversations (id, title, provider_id, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (conv_id, message[:50] + "..." if len(message) > 50 else message, provider.id, provider.model, time.time(), time.time()),
            )
            conversation_id = conv_id
            await self._handle_conversations_create({"title": message[:50]})

        now = time.time()
        await execute(
            "INSERT INTO messages (id, conversation_id, role, content, provider, model, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), conversation_id, "user", message, provider.id, provider.model, now),
        )
        await execute(
            "INSERT INTO messages (id, conversation_id, role, content, provider, model, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), conversation_id, "assistant", content, provider.id, provider.model, now),
        )
        await execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )

        return {"conversation_id": conversation_id, "provider": provider.id, "model": provider.model, "content": content}

    async def _handle_chat_stream(self, params: dict) -> dict:
        """Placeholder: streaming handled via _send_event during _handle_chat_stream."""
        provider_id = params.get("provider_id")
        message = params.get("message", "")
        conversation_id = params.get("conversation_id")

        provider = await self._get_provider_or_default(provider_id)
        from .providers.base import ChatMessage

        if not conversation_id:
            conv_id = str(uuid.uuid4())
            await execute(
                "INSERT INTO conversations (id, title, provider_id, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (conv_id, message[:50] + "..." if len(message) > 50 else message, provider.id, provider.model, time.time(), time.time()),
            )
            conversation_id = conv_id
            await self._handle_conversations_create({"title": message[:50]})

        now = time.time()
        await execute(
            "INSERT INTO messages (id, conversation_id, role, content, provider, model, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), conversation_id, "user", message, provider.id, provider.model, now),
        )

        # Start streaming in background
        asyncio.create_task(self._stream_chat(provider_id, [ChatMessage(role="user", content=message)], conversation_id, provider))

        return {"conversation_id": conversation_id, "streaming": True}

    async def _stream_chat(self, provider_id: str, messages: list, conversation_id: str, provider) -> None:
        from .providers.base import ChatResponse
        full_content = ""
        msg_id = str(uuid.uuid4())

        await self._send_event("chat_chunk_start", {
            "conversation_id": conversation_id,
            "message_id": msg_id,
            "provider": provider.id,
            "model": provider.model,
        })

        async for resp in provider.chat(messages):
            if resp.streaming:
                full_content += resp.content
                await self._send_event("chat_chunk", {
                    "conversation_id": conversation_id,
                    "message_id": msg_id,
                    "content": resp.content,
                })

        now = time.time()
        await execute(
            "INSERT INTO messages (id, conversation_id, role, content, provider, model, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, "assistant", full_content, provider.id, provider.model, now),
        )
        await execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        await self._send_event("chat_chunk_end", {
            "conversation_id": conversation_id,
            "message_id": msg_id,
            "content": full_content,
        })

    async def _get_provider_or_default(self, provider_id: str | None):
        if provider_id and provider_id in {p.id for p in manager.list_providers()}:
            return manager.get_provider(provider_id)
        default = manager.get_default_provider()
        if default is None:
            raise ProviderError(
                "No configured provider available.",
                details="Configure a provider with an API key via settings, or add a provider.",
            )
        return default

    async def _handle_providers_list(self, params: dict) -> list:
        return [p.model_dump() for p in manager.list_providers()]

    async def _handle_providers_add(self, params: dict) -> dict:
        provider_type = params.get("type", "openrouter")
        name = params.get("name", provider_type)
        model = params.get("model", "gpt-3.5-turbo")
        api_key = params.get("api_key")
        base_url = params.get("base_url")
        extra = params.get("extra")

        config = await manager.add_provider(
            provider_type=provider_type,
            name=name,
            model=model,
            api_key=api_key,
            base_url=base_url,
            extra=extra,
        )
        return {"id": config.id, "configured": config.configured}

    async def _handle_providers_remove(self, params: dict) -> dict:
        provider_id = params.get("id")
        if not provider_id:
            raise ProviderError("Provider ID required.")
        await manager.remove_provider(provider_id)
        return {"removed": provider_id}

    async def _handle_providers_test(self, params: dict) -> dict:
        provider_id = params.get("id")
        if not provider_id:
            raise ProviderError("Provider ID required.")
        result = await manager.test_connection(provider_id)
        return {"ok": result, "provider_id": provider_id}

    async def _handle_diagnostics(self, params: dict) -> list:
        results = await run_all_diagnostics()
        return [
            {"name": r.name, "status": r.status, "details": r.details, "remediation": r.remediation}
            for r in results
        ]

    async def _handle_conversations_list(self, params: dict) -> list:
        rows = await execute(
            "SELECT id, title, provider_id, model, created_at, updated_at FROM conversations ORDER BY updated_at DESC",
            fetch="all",
        )
        return rows or []

    async def _handle_conversations_create(self, params: dict) -> dict:
        title = params.get("title", "New conversation")
        conv_id = str(uuid.uuid4())
        provider_id = params.get("provider_id", "openrouter")
        model = params.get("model", "default")
        now = time.time()
        await execute(
            "INSERT INTO conversations (id, title, provider_id, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, title, provider_id, model, now, now),
        )
        return {"id": conv_id, "title": title}

    async def _handle_conversations_get(self, params: dict) -> dict:
        conv_id = params.get("conversation_id")
        if not conv_id:
            raise ProviderError("Conversation ID required.")

        conv = await execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,), fetch="one"
        )
        if conv is None:
            raise ProviderError(f"Conversation '{conv_id}' not found.")

        messages = await execute(
            "SELECT role, content, provider, model, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv_id,), fetch="all",
        )
        return {"conversation": conv, "messages": messages or []}

    async def _handle_settings_get(self, params: dict) -> dict:
        from .core.config import settings as cfg
        return {
            "server": cfg.server.model_dump(),
            "security": cfg.security.model_dump(),
            "ui": cfg.ui.model_dump(),
            "ai": cfg.ai.model_dump(),
        }

    async def _handle_settings_set(self, params: dict) -> dict:
        key = params.get("key")
        value = params.get("value")
        if not key:
            raise ProviderError("Settings key required.")
        # Store simple settings; nested settings handled by restart
        await execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value)),
        )
        return {"updated": key}

    async def _handle_shutdown(self, params: dict) -> dict:
        logger.info("Shutdown requested via IPC.")
        self._shutdown_requested = True
        asyncio.create_task(self.stop())
        return {"shutting_down": True}

    # --- HTTP fallback handlers ---

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "timestamp": time.time()})

    async def _http_chat(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body."}, status=400)
        try:
            provider = await self._get_provider_or_default(data.get("provider_id"))
            from .providers.base import ChatMessage

            messages = [ChatMessage(role="user", content=data.get("message", ""))]
            content = ""
            async for resp in provider.chat(messages, stream=False):
                content = resp.content
            return web.json_response({"provider": provider.id, "model": provider.model, "content": content})
        except ProviderError as e:
            return web.json_response({"error": str(e), "category": e.category, "details": e.details}, status=400)
        except Exception as e:
            logger.exception(f"Unhandled error in HTTP chat: {e}")
            return web.json_response({"error": "Internal server error.", "details": str(e)}, status=500)

    async def _http_list_providers(self, request: web.Request) -> web.Response:
        return web.json_response([p.model_dump() for p in manager.list_providers()])

    async def _http_diagnostics(self, request: web.Request) -> web.Response:
        results = await run_all_diagnostics()
        return web.json_response([
            {"name": r.name, "status": r.status, "details": r.details, "remediation": r.remediation}
            for r in results
        ])

    async def _http_list_conversations(self, request: web.Request) -> web.Response:
        rows = await execute(
            "SELECT id, title, provider_id, model, created_at, updated_at FROM conversations ORDER BY updated_at DESC",
            fetch="all",
        )
        return web.json_response(rows or [])

    async def _http_create_conversation(self, request: web.Request) -> web.Response:
        data = await request.json()
        title = data.get("title", "New conversation")
        conv_id = str(uuid.uuid4())
        now = time.time()
        await execute(
            "INSERT INTO conversations (id, title, provider_id, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, title, "openrouter", "default", now, now),
        )
        return web.json_response({"id": conv_id, "title": title})
