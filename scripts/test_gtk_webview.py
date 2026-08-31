#!/usr/bin/env python3
"""Minimal standalone GTK + WebKit2 + pywebview test.

Initializes GTK, verifies WebKit2, creates a pywebview window pointing
at the NEXORA IPC server, and stays open until manually closed.
"""
import os
import sys
import time
import threading
import asyncio

# Verify display before anything else
if not os.environ.get('DISPLAY'):
    print("FATAL: DISPLAY not set. Run on a graphical desktop.")
    sys.exit(1)

print(f"DISPLAY={os.environ['DISPLAY']}")
print(f"GDK_BACKEND={os.environ.get('GDK_BACKEND', '(not set)')}")

# 1. Verify gi / GTK / WebKit2 can be imported
print("\n--- Step 1: Verify gi / GTK / WebKit2 ---")
try:
    import gi
    print(f"  gi module: {gi.__file__}")
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    print("  GTK 3.0: OK")
    gi.require_version('WebKit2', '4.1')
    from gi.repository import WebKit2
    print("  WebKit2 4.1: OK")
except Exception as e:
    print(f"  FATAL: {e}")
    sys.exit(1)

# 2. Verify pywebview can initialize GTK backend
print("\n--- Step 2: Verify pywebview GTK backend ---")
try:
    import webview
    gtk_mod = webview.initialize('gtk')
    if gtk_mod is None:
        print("  FATAL: webview.initialize('gtk') returned None")
        sys.exit(1)
    print(f"  GTK backend loaded: {gtk_mod.__name__}")
    print(f"  Renderer: {gtk_mod.renderer}")
except Exception as e:
    print(f"  FATAL: {e}")
    sys.exit(1)

# 3. Start IPC backend (if available)
print("\n--- Step 3: Start NEXORA backend ---")
ipc = None
try:
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
    from app.core.db import init_db
    from app.providers import manager
    from app.ipc import IPCServer

    async def start_backend():
        global ipc
        await init_db()
        await manager.load_from_db()
        ipc = IPCServer()
        await ipc.start()
        return ipc

    ipc = asyncio.run(start_backend())
    print(f"  IPC server started: {ipc.get_url()}")
except Exception as e:
    print(f"  WARNING: Backend failed to start: {e}")
    print("  Will try loading URL directly anyway")

# 4. Create pywebview window
print("\n--- Step 4: Create pywebview window ---")
url = "http://127.0.0.1:8765/webui/"
print(f"  URL: {url}")

window = webview.create_window(
    title="N E X O R A — GTK Test",
    url=url,
    width=1280,
    height=800,
    min_size=(800, 600),
    resizable=True,
)

loaded = threading.Event()

def on_loaded():
    loaded.set()
    print("  Window loaded!")

window.events.loaded += on_loaded

# 5. Start pywebview (blocks until window closes)
print("\n--- Step 5: Starting pywebview (GTK) ---")
print("  Window should appear on screen now...")
print("  Close the window to exit.")

try:
    webview.start(gui='gtk', debug=True)
except KeyboardInterrupt:
    print("\n  Keyboard interrupt received.")
except Exception as e:
    print(f"\n  ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 6. Cleanup
print("\n--- Step 6: Cleanup ---")
if ipc:
    async def stop_backend():
        await ipc.stop()
        from app.providers import manager
        await manager.shutdown()
    asyncio.run(stop_backend())
    print("  Backend stopped.")

print("\n=== TEST COMPLETE ===")
print("If you saw a window with the NEXORA UI, the GTK backend works!")
