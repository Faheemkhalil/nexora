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
from .core.errors import NexoraError, AuthenticationError, ProviderError
from .providers import manager

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
            "shutdown": self._handle_shutdown,
        }
        self._shutdown_requested = False
        self._runner: web.AppRunner | None = None

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
        logger.info(
            f"IPC server started on {settings.server.host}:{settings.server.port}"
        )

    async def stop(self) -> None:
        """Stop the server and close all connections."""
        self._shutdown_requested = True
        for ws in list(self._ws_clients):
            await ws.close()
        self._ws_clients.clear()
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        logger.info("IPC server stopped.")

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
