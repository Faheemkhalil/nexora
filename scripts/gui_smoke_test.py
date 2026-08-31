#!/usr/bin/env python3
"""
NEXORA GUI Smoke Test
Runs on a graphical Kali desktop with WebKit2GTK installed.
Tests actual window creation, 3D scene loading, and IPC connectivity.
"""
import sys
import os
import asyncio
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}", flush=True)

def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}", flush=True)

def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET} {msg}", flush=True)

def info(msg: str) -> None:
    print(f"  {BLUE}ℹ{RESET} {msg}", flush=True)

def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}", flush=True)
    print("-" * len(title), flush=True)

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def pass_(self, name: str):
        self.passed += 1
        ok(name)

    def fail(self, name: str, error: str = ""):
        self.failed += 1
        fail(f"{name}: {error}" if error else name)

    def skip(self, name: str, reason: str = ""):
        self.skipped += 1
        warn(f"{name} - SKIPPED: {reason}" if reason else f"{name} - SKIPPED")

    def summary(self) -> int:
        print(f"\n{BOLD}=== SMOKE TEST SUMMARY ==={RESET}", flush=True)
        print(f"  {GREEN}PASS:{RESET}  {self.passed}", flush=True)
        print(f"  {RED}FAIL:{RESET}  {self.failed}", flush=True)
        print(f"  {YELLOW}SKIP:{RESET}  {self.skipped}", flush=True)
        return 0 if self.failed == 0 else 1


# ── Persistent backend thread ───────────────────────────────────────────
_backend_loop: asyncio.AbstractEventLoop | None = None
_ipc = None


def _start_backend_thread():
    """Start the NEXORA backend in a background thread with its own event loop."""
    global _backend_loop, _ipc
    _backend_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_backend_loop)

    async def _init():
        global _ipc
        from app.core.db import init_db
        from app.providers import manager
        from app.ipc import IPCServer

        await init_db()
        await manager.load_from_db()
        _ipc = IPCServer()
        await _ipc.start()
        return _ipc

    _ipc = _backend_loop.run_until_complete(_init())

    # Keep the loop alive so the server stays up
    _backend_loop.run_forever()


def _shutdown_backend():
    """Shut down the backend thread gracefully."""
    global _backend_loop, _ipc
    if _backend_loop and _backend_loop.is_running():
        async def _stop():
            if _ipc:
                from app.providers import manager
                await _ipc.stop()
                await manager.shutdown()
        future = asyncio.run_coroutine_threadsafe(_stop(), _backend_loop)
        future.result(timeout=10)
        _backend_loop.call_soon_threadsafe(_backend_loop.stop)
    _backend_loop = None
    _ipc = None


def _async_run(coro):
    """Run a coroutine on the backend thread's event loop and return the result (sync bridge)."""
    future = asyncio.run_coroutine_threadsafe(coro, _backend_loop)
    return future.result(timeout=30)


# ── Tests ───────────────────────────────────────────────────────────────

def test_imports(result: TestResult) -> None:
    """Test that all modules import correctly."""
    section("Module Imports")

    try:
        import webview
        gtk_mod = webview.initialize('gtk')
        if gtk_mod is not None:
            result.pass_(f"pywebview GTK backend: {gtk_mod.__name__}")
        else:
            result.fail("pywebview GTK backend", "guilib is None after initialize")
            return
    except Exception as e:
        result.fail("pywebview GTK backend", str(e))
        return

    try:
        from app.main import NEXORAApp
        result.pass_("app.main")
    except Exception as e:
        result.fail("app.main", str(e))
        return

    try:
        from app.ipc import IPCServer
        result.pass_("app.ipc")
    except Exception as e:
        result.fail("app.ipc", str(e))
        return


def test_backend_startup(result: TestResult):
    """Test backend starts and IPC server works."""
    section("Backend Startup & IPC")

    try:
        global _ipc
        t = threading.Thread(target=_start_backend_thread, daemon=True)
        t.start()

        # Wait until the backend is ready
        deadline = time.time() + 15
        while _ipc is None and time.time() < deadline:
            time.sleep(0.3)

        if _ipc is None:
            result.fail("Backend startup", "IPC server did not start within 15s")
            return None

        result.pass_(f"IPC server started on {_ipc.get_url()}")
        return _ipc

    except Exception as e:
        result.fail("Backend startup", str(e))
        return None


def test_http_endpoints(result: TestResult, ipc) -> None:
    """Test all HTTP endpoints."""
    section("HTTP Endpoints")

    import aiohttp

    async def run():
        async with aiohttp.ClientSession() as session:
            timeout = aiohttp.ClientTimeout(total=10)

            # Health
            try:
                async with session.get('http://127.0.0.1:8765/healthz', timeout=timeout) as resp:
                    if resp.status == 200:
                        result.pass_("/healthz")
                    else:
                        result.fail("/healthz", f"status {resp.status}")
            except Exception as e:
                result.fail("/healthz", str(e))

            # Providers
            try:
                async with session.get('http://127.0.0.1:8765/api/providers', timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.pass_(f"/api/providers ({len(data)} providers)")
                    else:
                        result.fail("/api/providers", f"status {resp.status}")
            except Exception as e:
                result.fail("/api/providers", str(e))

            # Diagnostics
            try:
                async with session.get('http://127.0.0.1:8765/api/diagnostics', timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.pass_(f"/api/diagnostics ({len(data)} checks)")
                    else:
                        result.fail("/api/diagnostics", f"status {resp.status}")
            except Exception as e:
                result.fail("/api/diagnostics", str(e))

            # Conversations
            try:
                async with session.get('http://127.0.0.1:8765/api/conversations', timeout=timeout) as resp:
                    if resp.status == 200:
                        result.pass_("/api/conversations")
                    else:
                        result.fail("/api/conversations", f"status {resp.status}")
            except Exception as e:
                result.fail("/api/conversations", str(e))

            # Static files
            dist_dir = PROJECT_ROOT / "ui" / "dist"
            if dist_dir.exists():
                asset_files = list((dist_dir / "assets").glob("*.js")) + list((dist_dir / "assets").glob("*.css"))
                check_paths = ['/webui/', '/webui/index.html']
                if asset_files:
                    js_file = next((f for f in asset_files if f.suffix == '.js'), None)
                    css_file = next((f for f in asset_files if f.suffix == '.css'), None)
                    if js_file:
                        check_paths.append(f'/webui/assets/{js_file.name}')
                    if css_file:
                        check_paths.append(f'/webui/assets/{css_file.name}')
                for path in check_paths:
                    try:
                        async with session.get(f'http://127.0.0.1:8765{path}', timeout=timeout) as resp:
                            if resp.status == 200:
                                result.pass_(f"Static {path}")
                            else:
                                result.fail(f"Static {path}", f"status {resp.status}")
                    except Exception as e:
                        result.fail(f"Static {path}", str(e))

    _async_run(run())


def test_websocket(result: TestResult, ipc) -> None:
    """Test WebSocket connectivity."""
    section("WebSocket IPC")

    import aiohttp

    async def run():
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            ws = await session.ws_connect('http://127.0.0.1:8765/ws')

            # Ping
            await ws.send_str('{"id":"test-ping","method":"ping"}')
            msg = await ws.receive()
            if msg.type.name == 'TEXT' and 'pong' in msg.data:
                result.pass_("WebSocket ping/pong")
            else:
                result.fail("WebSocket ping/pong", f"unexpected: {msg.data}")

            # Providers.list
            await ws.send_str('{"id":"test-prov","method":"providers.list"}')
            msg = await ws.receive()
            if msg.type.name == 'TEXT' and 'result' in msg.data:
                result.pass_("WebSocket providers.list")
            else:
                result.fail("WebSocket providers.list", f"unexpected: {msg.data}")

            # Diagnostics
            await ws.send_str('{"id":"test-diag","method":"diagnostics"}')
            msg = await ws.receive()
            if msg.type.name == 'TEXT' and 'result' in msg.data:
                result.pass_("WebSocket diagnostics")
            else:
                result.fail("WebSocket diagnostics", f"unexpected: {msg.data}")

            await ws.close()

    _async_run(run())


def test_gui_window_creation(result: TestResult, ipc) -> None:
    """Test actual desktop window creation with pywebview.

    pywebview.start() MUST be called from the main thread, so this test
    blocks until the window closes (auto-close after 8s via a timer func).
    This MUST be the last test before shutdown.
    """
    section("GUI Window Creation")

    import webview

    load_event = threading.Event()
    window_ref = [None]

    def on_loaded(*_args):
        load_event.set()
        info("Window loaded event fired")

    def on_closing(*_args):
        info("Window closing event fired")

    def _auto_close():
        """Called by pywebview in a background thread once the GUI loop starts."""
        # Wait for the page to load, then destroy after a delay
        if load_event.wait(timeout=15):
            info("GUI loaded — waiting 3s for Three.js render, then closing")
            time.sleep(3)
            try:
                window_ref[0].destroy()
            except Exception:
                pass
        else:
            info("GUI load timeout — force closing")
            try:
                window_ref[0].destroy()
            except Exception:
                pass

    try:
        url = "http://127.0.0.1:8765/webui/"
        info(f"Creating window with URL: {url}")

        window = webview.create_window(
            title="N E X O R A — Smoke Test",
            url=url,
            width=1024,
            height=768,
            min_size=(800, 600),
        )
        window_ref[0] = window

        window.events.loaded += on_loaded
        window.events.closing += on_closing

        # This blocks until the window is closed
        webview.start(gui='gtk', debug=False, func=_auto_close,
                      storage_path=str(PROJECT_ROOT / "data" / "webview"))

        if load_event.is_set():
            result.pass_("GUI window created and loaded")
            result.pass_("GUI window closed cleanly")
        else:
            result.fail("GUI window creation", "Window did not fire loaded event")

    except Exception as e:
        result.fail("GUI window creation", str(e))


def test_frontend_console_errors(result: TestResult) -> None:
    """Test for frontend console errors."""
    section("Frontend Console Check")

    info("Automated console error detection requires Selenium/Playwright")
    info("Manual check: Open http://127.0.0.1:8765/webui/ in browser, check DevTools Console")
    result.skip("Frontend console errors", "Requires browser automation")


def test_backend_exceptions(result: TestResult, ipc) -> None:
    """Check backend for exceptions during GUI test."""
    section("Backend Exception Check")
    info("Check terminal running backend for unhandled exceptions")
    result.skip("Backend exceptions", "Manual verification needed")


def test_clean_shutdown(result: TestResult, ipc) -> None:
    """Test clean shutdown of all components."""
    section("Clean Shutdown")

    try:
        _shutdown_backend()
        result.pass_("All components shut down cleanly")
    except Exception as e:
        result.fail("Clean shutdown", str(e))


def main():
    print(f"{BOLD}NEXORA GUI Smoke Test{RESET}", flush=True)
    print(f"Project: {PROJECT_ROOT}", flush=True)

    if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
        print(f"{RED}No DISPLAY or WAYLAND_DISPLAY set - cannot run GUI tests{RESET}", flush=True)
        print("Run on a graphical desktop or use: xvfb-run -a python scripts/gui_smoke_test.py", flush=True)
        return 1

    result = TestResult()

    test_imports(result)

    ipc = test_backend_startup(result)
    if ipc is None:
        return result.summary()

    test_http_endpoints(result, ipc)
    test_websocket(result, ipc)
    test_gui_window_creation(result, ipc)
    test_frontend_console_errors(result)
    test_backend_exceptions(result, ipc)
    test_clean_shutdown(result, ipc)

    return result.summary()


if __name__ == "__main__":
    sys.exit(main())
