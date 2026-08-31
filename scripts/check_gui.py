#!/usr/bin/env python3
"""
NEXORA GUI Environment Diagnostic Script
Checks all prerequisites for running the NEXORA desktop application.
"""

import os
import sys
import subprocess
import platform
import importlib.util
from pathlib import Path
from typing import List, Tuple

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")

def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET} {msg}")

def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")

def info(msg: str) -> None:
    print(f"  {BLUE}ℹ{RESET} {msg}")

def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")
    print("-" * len(title))

def check_display_environment() -> List[Tuple[bool, str]]:
    """Check display server environment."""
    results = []

    section("Display Environment")

    # Check X11
    display = os.environ.get('DISPLAY')
    if display:
        ok(f"DISPLAY={display}")
        results.append((True, f"DISPLAY={display}"))
    else:
        fail("DISPLAY not set")
        results.append((False, "DISPLAY not set"))

    # Check Wayland
    wayland_display = os.environ.get('WAYLAND_DISPLAY')
    if wayland_display:
        ok(f"WAYLAND_DISPLAY={wayland_display}")
        results.append((True, f"WAYLAND_DISPLAY={wayland_display}"))
    else:
        info("WAYLAND_DISPLAY not set (X11 assumed)")
        results.append((True, "WAYLAND_DISPLAY not set"))

    # Check X11 server connectivity
    if display:
        try:
            result = subprocess.run(
                ['xset', 'q'],
                capture_output=True,
                timeout=3
            )
            if result.returncode == 0:
                ok("X11 server reachable")
                results.append((True, "X11 server reachable"))
            else:
                fail("X11 server not reachable")
                results.append((False, "X11 server not reachable"))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            fail("xset command failed or timeout")
            results.append((False, "xset command failed"))

    return results

def check_system_packages() -> List[Tuple[bool, str]]:
    """Check required system packages."""
    results = []

    section("System Packages (Debian/Kali)")

    required_packages = {
        'gir1.2-webkit2-4.1': 'WebKit2GTK GObject introspection (REQUIRED for pywebview GTK)',
        'libwebkit2gtk-4.1-0': 'WebKit2GTK runtime library',
        'libwebkit2gtk-4.1-dev': 'WebKit2GTK development headers (optional)',
        'python3-gi': 'Python GObject introspection bindings',
        'python3-gi-cairo': 'Python Cairo bindings for GTK',
        'xvfb': 'Virtual framebuffer (for headless testing)',
    }

    for pkg, desc in required_packages.items():
        try:
            result = subprocess.run(
                ['dpkg', '-l', pkg],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and 'ii' in result.stdout:
                ok(f"{pkg} - {desc}")
                results.append((True, pkg))
            else:
                if 'REQUIRED' in desc:
                    fail(f"{pkg} - {desc}")
                else:
                    warn(f"{pkg} - {desc}")
                results.append((False, pkg))
        except Exception:
            fail(f"Could not check {pkg}")
            results.append((False, pkg))

    return results

def check_python_gi_bindings() -> List[Tuple[bool, str]]:
    """Check Python GI and WebKit2 bindings."""
    results = []

    section("Python GI Bindings")

    # Check gi module
    try:
        import gi
        ok("gi module available")
        results.append((True, "gi module"))
    except ImportError:
        fail("gi module NOT available (install python3-gi)")
        results.append((False, "gi module"))
        return results

    # Check WebKit2 4.1
    try:
        gi.require_version('WebKit2', '4.1')
        from gi.repository import WebKit2
        ok("WebKit2 4.1 bindings available")
        results.append((True, "WebKit2 4.1"))
    except (ValueError, ImportError) as e:
        fail(f"WebKit2 4.1 bindings NOT available: {e}")
        results.append((False, "WebKit2 4.1"))

    # Check WebKit2 4.0 (fallback)
    try:
        gi.require_version('WebKit2', '4.0')
        from gi.repository import WebKit2 as WebKit2_4_0
        ok("WebKit2 4.0 bindings available (fallback)")
        results.append((True, "WebKit2 4.0"))
    except (ValueError, ImportError):
        info("WebKit2 4.0 bindings not available (using 4.1)")
        results.append((True, "WebKit2 4.0 (not needed)"))

    # Check GTK 3.0/4.0
    for version in ['3.0', '4.0']:
        try:
            gi.require_version('Gtk', version)
            from gi.repository import Gtk
            ok(f"GTK {version} bindings available")
            results.append((True, f"GTK {version}"))
            break
        except (ValueError, ImportError):
            continue
    else:
        fail("No GTK bindings available")
        results.append((False, "GTK"))

    return results

def check_pywebview() -> List[Tuple[bool, str]]:
    """Check pywebview installation and backend."""
    results = []

    section("pywebview")

    try:
        import webview
        import importlib.metadata
        version = importlib.metadata.version('pywebview')
        ok(f"pywebview {version} installed")
        results.append((True, f"pywebview {version}"))
    except ImportError:
        fail("pywebview NOT installed")
        results.append((False, "pywebview"))
        return results
    except Exception as e:
        fail(f"pywebview error: {e}")
        results.append((False, "pywebview"))
        return results

    # Check available backends — use the return value of initialize()
    # (webview.guilib may be shadowed by a module-level `guilib = None`)
    try:
        gtk_mod = webview.initialize('gtk')
        if gtk_mod is not None:
            ok(f"GTK backend: {gtk_mod.__name__}")
            ok(f"Renderer: {gtk_mod.renderer}")
            results.append((True, f"GTK backend: {gtk_mod.__name__}"))
        else:
            fail("GTK backend failed to initialize")
            results.append((False, "GTK backend"))
    except Exception as e:
        fail(f"GTK backend initialization failed: {e}")
        results.append((False, "GTK backend"))

    # Check other backends
    for backend in ['qt', 'cef']:
        try:
            webview.initialize(backend)
            if webview.guilib:
                info(f"{backend.upper()} backend also available: {webview.guilib.__name__}")
        except Exception:
            pass

    return results

def check_frontend_assets() -> List[Tuple[bool, str]]:
    """Check frontend source assets."""
    results = []

    section("Frontend Assets")

    project_root = Path(__file__).parent.parent
    ui_dir = project_root / "ui"
    src_dir = ui_dir / "src"

    required_files = [
        ("index.html", ui_dir / "index.html"),
        ("package.json", ui_dir / "package.json"),
        ("tsconfig.json", ui_dir / "tsconfig.json"),
        ("vite.config.ts", ui_dir / "vite.config.ts"),
        ("src/main.ts", src_dir / "main.ts"),
        ("src/app.ts", src_dir / "app.ts"),
        ("src/styles/main.css", src_dir / "styles" / "main.css"),
        ("src/lib/ipc.ts", src_dir / "lib" / "ipc.ts"),
        ("src/scenes/ThreeScene.ts", src_dir / "scenes" / "ThreeScene.ts"),
        ("src/components/Sidebar.ts", src_dir / "components" / "Sidebar.ts"),
        ("src/components/ChatOverlay.ts", src_dir / "components" / "ChatOverlay.ts"),
        ("src/components/RightPanel.ts", src_dir / "components" / "RightPanel.ts"),
        ("src/components/StatusBar.ts", src_dir / "components" / "StatusBar.ts"),
        ("src/screens/SettingsModal.ts", src_dir / "screens" / "SettingsModal.ts"),
        ("src/screens/DiagnosticsModal.ts", src_dir / "screens" / "DiagnosticsModal.ts"),
    ]

    all_ok = True
    for name, path in required_files:
        if path.exists():
            ok(f"{name}")
            results.append((True, name))
        else:
            fail(f"{name} - MISSING at {path}")
            results.append((False, name))
            all_ok = False

    # Check package.json
    pkg_json = ui_dir / "package.json"
    if pkg_json.exists():
        ok("package.json")
        results.append((True, "package.json"))
    else:
        fail("package.json - MISSING")
        results.append((False, "package.json"))

    # Check dist/ (built assets)
    dist_dir = ui_dir / "dist"
    dist_index = dist_dir / "index.html"
    dist_assets = dist_dir / "assets"
    if dist_dir.exists():
        info("dist/ directory exists (built assets)")
        results.append((True, "dist/ (built)"))
        if dist_index.exists():
            ok("dist/index.html")
            results.append((True, "dist/index.html"))
        else:
            fail("dist/index.html - MISSING")
            results.append((False, "dist/index.html"))
        if dist_assets.exists() and any(dist_assets.iterdir()):
            ok("dist/assets/ (built JS/CSS)")
            results.append((True, "dist/assets/"))
        else:
            warn("dist/assets/ empty or missing")
            results.append((False, "dist/assets/"))
    else:
        warn("dist/ directory NOT found - run 'npm run build' in ui/")
        results.append((False, "dist/ (not built)"))

    return results

def check_backend_imports() -> List[Tuple[bool, str]]:
    """Check that backend modules import correctly."""
    results = []

    section("Backend Module Imports")

    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    modules = [
        "app.core.config",
        "app.core.db",
        "app.core.logging",
        "app.core.secrets",
        "app.core.errors",
        "app.core.diagnostics",
        "app.providers.base",
        "app.providers.manager",
        "app.providers.openrouter",
        "app.providers.custom",
        "app.providers.local",
        "app.ipc",
        "app.main",
    ]

    for mod in modules:
        try:
            __import__(mod)
            ok(f"{mod}")
            results.append((True, mod))
        except Exception as e:
            fail(f"{mod}: {e}")
            results.append((False, mod))

    return results

def check_backend_startup() -> List[Tuple[bool, str]]:
    """Test backend startup sequence."""
    results = []

    section("Backend Startup Test")

    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    try:
        import asyncio
        from app.core.db import init_db
        from app.providers import manager
        from app.ipc import IPCServer
        from app.main import NEXORAApp

        async def test():
            # Initialize database
            await init_db()
            ok("Database initialized")

            # Load providers
            await manager.load_from_db()
            providers = manager.list_providers()
            ok(f"Loaded {len(providers)} provider(s)")

            # Start IPC server
            ipc = IPCServer()
            await ipc.start()
            ok(f"IPC server started on {ipc.get_url()}")

            # Test HTTP endpoints
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('http://127.0.0.1:8765/healthz') as resp:
                    if resp.status == 200:
                        ok("/healthz endpoint OK")
                    else:
                        fail(f"/healthz returned {resp.status}")

                async with session.get('http://127.0.0.1:8765/api/providers') as resp:
                    if resp.status == 200:
                        ok("/api/providers endpoint OK")
                    else:
                        fail(f"/api/providers returned {resp.status}")

                async with session.get('http://127.0.0.1:8765/api/diagnostics') as resp:
                    if resp.status == 200:
                        ok("/api/diagnostics endpoint OK")
                    else:
                        fail(f"/api/diagnostics returned {resp.status}")

                # Test WebSocket
                ws = await session.ws_connect('http://127.0.0.1:8765/ws')
                await ws.send_str('{"id":"test","method":"ping"}')
                msg = await ws.receive()
                if msg.type.name == 'TEXT' and 'pong' in msg.data:
                    ok("WebSocket ping/pong OK")
                else:
                    fail("WebSocket ping/pong failed")
                await ws.close()

            await ipc.stop()
            await manager.shutdown()
            ok("Backend shutdown clean")
            return True

        asyncio.run(test())
        results.append((True, "Full backend startup"))

    except Exception as e:
        fail(f"Backend startup failed: {e}")
        results.append((False, "Full backend startup"))

    return results

def check_ipc_static_serving() -> List[Tuple[bool, str]]:
    """Test static file serving via IPC."""
    results = []

    section("IPC Static File Serving")

    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    try:
        import asyncio
        from app.ipc import IPCServer
        import aiohttp

        async def test():
            ipc = IPCServer()
            await ipc.start()

            async with aiohttp.ClientSession() as session:
                dist_dir = project_root / "ui" / "dist"
                is_built = dist_dir.exists()

                # Test index.html
                async with session.get('http://127.0.0.1:8765/webui/') as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        if 'N E X O R A' in text or 'NEXORA' in text:
                            ok("UI index.html served correctly")
                        else:
                            warn("UI index.html served but content unexpected")
                    else:
                        fail(f"UI index.html returned {resp.status}")

                if is_built:
                    # Test built assets - check individual files (directory listing returns 403)
                    from glob import glob
                    js_files = glob(str(dist_dir / "assets" / "*.js"))
                    css_files = glob(str(dist_dir / "assets" / "*.css"))
                    asset_checks = []
                    if js_files:
                        asset_checks.append(f'/webui/assets/{Path(js_files[0]).name}')
                    if css_files:
                        asset_checks.append(f'/webui/assets/{Path(css_files[0]).name}')
                    for path in asset_checks:
                        async with session.get(f'http://127.0.0.1:8765{path}') as resp:
                            if resp.status == 200:
                                ok(f"dist/assets/{Path(path).name} served")
                            else:
                                fail(f"dist/assets/{Path(path).name} returned {resp.status}")
                    async with session.get('http://127.0.0.1:8765/webui/index.html') as resp:
                        if resp.status == 200:
                            ok("dist/index.html served")
                        else:
                            fail(f"dist/index.html returned {resp.status}")
                else:
                    # Test source files when not built
                    async with session.get('http://127.0.0.1:8765/webui/src/main.ts') as resp:
                        if resp.status == 200:
                            ok("src/main.ts served")
                        else:
                            fail(f"src/main.ts returned {resp.status}")

                    async with session.get('http://127.0.0.1:8765/webui/src/styles/main.css') as resp:
                        if resp.status == 200:
                            ok("src/styles/main.css served")
                        else:
                            fail(f"src/styles/main.css returned {resp.status}")

                    async with session.get('http://127.0.0.1:8765/webui/src/scenes/ThreeScene.ts') as resp:
                        if resp.status == 200:
                            ok("src/scenes/ThreeScene.ts served")
                        else:
                            fail(f"src/scenes/ThreeScene.ts returned {resp.status}")

            await ipc.stop()

        asyncio.run(test())
        results.append((True, "Static file serving"))

    except Exception as e:
        fail(f"Static file serving test failed: {e}")
        results.append((False, "Static file serving"))

    return results

def main():
    print(f"{BOLD}NEXORA GUI Environment Diagnostic{RESET}")
    print(f"Python: {platform.python_version()}")
    print(f"Platform: {platform.platform()}")
    print(f"Architecture: {platform.machine()}")

    all_results = []

    all_results.extend(check_display_environment())
    all_results.extend(check_system_packages())
    all_results.extend(check_python_gi_bindings())
    all_results.extend(check_pywebview())
    all_results.extend(check_frontend_assets())
    all_results.extend(check_backend_imports())
    all_results.extend(check_backend_startup())
    all_results.extend(check_ipc_static_serving())

    # Summary
    section("SUMMARY")
    passed = sum(1 for r in all_results if r[0])
    total = len(all_results)

    for success, name in all_results:
        status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
        print(f"  {status}  {name}")

    print(f"\n{BOLD}Overall: {passed}/{total} checks passed{RESET}")

    if passed == total:
        print(f"{GREEN}Environment ready for NEXORA GUI!{RESET}")
        return 0
    else:
        print(f"{RED}Environment NOT ready - fix failures above{RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())