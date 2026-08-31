"""NEXORA — main application entry point.

Bootstraps the backend: database, providers, IPC server, and the desktop shell.
"""
from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

from .core.config import settings
from .core.db import init_db
from .ipc import IPCServer
from .providers import manager


class NEXORAApp:
    """Top-level application controller."""

    def __init__(self) -> None:
        self.ipc: IPCServer | None = None
        self._running = False

    async def startup(self) -> None:
        """Initialize all subsystems."""
        logger.info("=== NEXORA Starting ===")
        logger.info(f"Python {sys.version.split()[0]}")

        # 1. Database
        await init_db()

        # 2. Providers
        await manager.load_from_db()
        logger.info(f"Loaded {len(manager.list_providers())} provider(s).")

        # 3. IPC server
        self.ipc = IPCServer()
        await self.ipc.start()
        logger.info(f"IPC server URL: {self.ipc.get_url()}")

        self._running = True
        logger.info("=== NEXORA Ready ===")

    async def run_desktop(self) -> None:
        """Start the backend and launch the desktop window.

        The asyncio event loop (with aiohttp) runs in a daemon thread
        so that pywebview's blocking GTK main loop does not starve it.
        """
        import threading

        # --- Background thread: asyncio loop with aiohttp IPC server ---
        self._bg_loop: asyncio.AbstractEventLoop | None = None
        _startup_error: Exception | None = None

        def _bg_entry():
            nonlocal _startup_error
            self._bg_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._bg_loop)
            try:
                self._bg_loop.run_until_complete(self.startup())
                self._bg_loop.run_forever()
            except Exception as exc:
                _startup_error = exc
                logger.error(f"Background loop error: {exc}")

        bg_thread = threading.Thread(target=_bg_entry, daemon=True)
        bg_thread.start()

        # Wait for startup to complete (poll until IPC is ready)
        import time as _time
        for _ in range(50):  # up to 5 seconds
            _time.sleep(0.1)
            if self.ipc is not None or _startup_error is not None:
                break
        if _startup_error:
            raise _startup_error

        logger.info("Background asyncio thread running.")

        # --- Main thread: pywebview GTK window ---
        import webview

        url = f"http://{settings.server.host}:{settings.server.port}/webui/"
        logger.info(f"Opening desktop window to: {url}")

        window = webview.create_window(
            title="N E X O R A",
            url=url,
            width=1280,
            height=800,
            min_size=(800, 600),
            resizable=True,
            fullscreen=settings.ui.fullscreen,
        )

        def on_closing():
            logger.info("Window closing — initiating shutdown.")
            if self._bg_loop and self._bg_loop.is_running():
                self._bg_loop.call_soon_threadsafe(self.shutdown_sync)

        window.events.closing += on_closing

        try:
            webview.start(
                func=None,
                gui="gtk",
                debug=False,
            )
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received.")
        finally:
            await self.shutdown()

    async def run_headless(self) -> None:
        """Start the backend only (no desktop window)."""
        await self.startup()
        logger.info("Running in headless mode. Press Ctrl+C to shutdown.")
        try:
            while self._running and self.ipc and not self.ipc.shutdown_requested:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.shutdown()

    async def _heartbeat(self) -> None:
        """Periodic maintenance heartbeat."""
        while True:
            await asyncio.sleep(30)
            if self.ipc and self.ipc.shutdown_requested:
                logger.info("Shutdown detected via heartbeat.")
                break

    def shutdown_sync(self) -> None:
        """Synchronous shutdown helper — call from a non-async context."""
        if self._bg_loop and self._bg_loop.is_running():
            asyncio.run_coroutine_threadsafe(self.shutdown(), self._bg_loop)

    async def shutdown(self) -> int:
        """Graceful shutdown of all subsystems."""
        if not self._running:
            return 0
        logger.info("=== NEXORA Shutting Down ===")
        self._running = False

        if self.ipc:
            await self.ipc.stop()
            self.ipc = None

        await manager.shutdown()
        logger.info("=== NEXORA Stopped ===")

        # Stop the background loop if running
        if self._bg_loop and self._bg_loop.is_running():
            self._bg_loop.call_soon_threadsafe(self._bg_loop.stop)

        return 0


async def _async_main() -> int:
    app = NEXORAApp()

    if "--headless" in sys.argv:
        def handle_signal():
            asyncio.create_task(app.shutdown())
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)
        await app.run_headless()
    else:
        await app.run_desktop()

    return 0


def main() -> None:
    """Sync entry point."""
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        logger.info("Interrupted.")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
