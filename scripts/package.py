#!/usr/bin/env python3
"""NEXORA — Packaging Script

Builds NEXORA as a standalone desktop application using PyInstaller.

Usage:
    python3 scripts/package.py              # Build for current platform
    python3 scripts/package.py --clean       # Clean build artifacts first
    python3 scripts/package.py --onefile     # Single executable (slower startup)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
APP_DIR = PROJECT_ROOT / "app"
UI_DIST = PROJECT_ROOT / "ui" / "dist"


def build_frontend() -> bool:
    """Build the Vite frontend."""
    print("Building frontend...")
    ui_dir = PROJECT_ROOT / "ui"
    result = subprocess.run(
        ["npm", "run", "build"],
        capture_output=True, text=True, cwd=ui_dir,
    )
    if result.returncode != 0:
        print(f"  Frontend build failed:\n{result.stderr[-1000:]}")
        return False
    print("  Frontend built")
    return True


def clean_build() -> None:
    """Clean build artifacts."""
    print("Cleaning build artifacts...")
    for d in [DIST_DIR, BUILD_DIR, PROJECT_ROOT / "nexora.spec"]:
        if d.is_dir():
            shutil.rmtree(d)
            print(f"  Removed {d}")
        elif d.is_file():
            d.unlink()
            print(f"  Removed {d}")
    print("  Clean")


def create_pyinstaller_spec(onefile: bool = False) -> Path:
    """Generate the PyInstaller spec file."""
    hidden = [
        "app", "app.core", "app.core.config", "app.core.db",
        "app.core.diagnostics", "app.core.errors", "app.core.logging",
        "app.core.memory", "app.core.secrets", "app.core.local_ai",
        "app.core.updater", "app.core.crash_reporter", "app.core.analytics",
        "app.providers", "app.providers.base", "app.providers.manager",
        "app.providers.openrouter", "app.providers.custom", "app.providers.local",
        "app.voice", "app.voice.stt", "app.voice.tts", "app.voice.microphone", "app.voice.voice_manager",
        "app.tools", "app.tools.base", "app.tools.registry", "app.tools.permissions",
        "app.tools.file_tools", "app.tools.system_tools", "app.tools.terminal_tools", "app.tools.app_tools",
        "app.coding", "app.coding.code_editor", "app.coding.git_ops",
        "app.coding.test_runner", "app.coding.ai_agent", "app.coding.project_manager",
        "app.internet", "app.internet.search", "app.internet.fetch", "app.internet.docs", "app.internet.browser",
        "app.security", "app.security.findings", "app.security.lab", "app.security.reports", "app.security.scope",
        "app.plugins", "app.plugins.loader", "app.plugins.marketplace", "app.plugins.community",
        "app.ipc",
        "aiohttp", "aiosqlite", "pydantic", "pydantic_settings", "loguru", "httpx",
        "webview", "webview.platforms.gtk",
    ]

    hidden_str = ",\n        ".join(f"'{h}'" for h in hidden)

    datas_items = []
    if UI_DIST.exists():
        datas_items.append(f"(str(ui_dist), 'ui/dist')")
    data_dir = PROJECT_ROOT / "data"
    if data_dir.exists():
        datas_items.append(f"(str(project_root / 'data'), 'data')")
    datas_str = ",\n        ".join(datas_items) if datas_items else ""

    if onefile:
        exe_line = (
            "exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [], "
            'name="NEXORA", debug=False, strip=False, upx=True, console=False)'
        )
        collect_line = ""
    else:
        exe_line = (
            "exe = EXE(pyz, a.scripts, [], exclude_binaries=True, "
            'name="NEXORA", debug=False, strip=False, upx=True, console=False)'
        )
        collect_line = 'coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name="NEXORA")'

    spec = f"""# -*- mode: python ; coding: utf-8 -*-
# NEXORA PyInstaller Spec

import os
from pathlib import Path

block_cipher = None
project_root = Path(r'{PROJECT_ROOT}')
ui_dist = project_root / 'ui' / 'dist'

a = Analysis(
    [str(project_root / 'app' / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        {datas_str},
    ],
    hiddenimports=[
        {hidden_str},
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy", "PIL"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

{exe_line}

{collect_line}
"""

    spec_path = PROJECT_ROOT / "nexora.spec"
    spec_path.write_text(spec)
    print(f"  Spec file: {spec_path}")
    return spec_path


def run_pyinstaller(spec_path: Path, onefile: bool = False) -> bool:
    """Run PyInstaller."""
    print("Building standalone app with PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"  PyInstaller failed:\n{result.stderr[-2000:]}")
        return False

    print("  Build complete")
    return True


def create_launcher_script() -> None:
    """Create a cross-platform launcher script."""
    launcher = DIST_DIR / "NEXORA" / "NEXORA"
    if launcher.exists():
        launcher.chmod(0o755)
        print(f"  Launcher: {launcher}")


def create_desktop_entry() -> None:
    """Create a .desktop file for Linux."""
    desktop_content = f"""[Desktop Entry]
Name=NEXORA
Comment=Personal AI Command & Security System
Exec={DIST_DIR / 'NEXORA' / 'NEXORA'}
Icon={PROJECT_ROOT / 'icon.png'}
Terminal=false
Type=Application
Categories=Development;Security;Utility;
Keywords=AI;security;terminal;coding;
"""
    desktop_path = DIST_DIR / "NEXORA" / "nexora.desktop"
    desktop_path.write_text(desktop_content)
    print(f"  Desktop entry: {desktop_path}")


def create_installer_script() -> None:
    """Create a simple install script."""
    install_content = f"""#!/bin/bash
# NEXORA Installer
INSTALL_DIR="$HOME/.local/share/nexora"
mkdir -p "$INSTALL_DIR"
cp -r "{DIST_DIR / 'NEXORA'}" "$INSTALL_DIR/"
ln -sf "$INSTALL_DIR/NEXORA/NEXORA" "$HOME/.local/bin/nexora" 2>/dev/null || true
echo "NEXORA installed to $INSTALL_DIR"
echo "Run: nexora"
"""
    install_path = DIST_DIR / "NEXORA" / "install.sh"
    install_path.write_text(install_content)
    install_path.chmod(0o755)
    print(f"  Installer: {install_path}")


def print_build_summary(onefile: bool) -> None:
    """Print build summary."""
    print("\n" + "=" * 60)
    print("NEXORA BUILD SUMMARY")
    print("=" * 60)

    exe = DIST_DIR / "NEXORA" / "NEXORA"
    if onefile:
        exe = DIST_DIR / "NEXORA.exe" if sys.platform == "win32" else DIST_DIR / "NEXORA"

    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"  Executable: {exe}")
        print(f"  Size: {size_mb:.1f} MB")
    else:
        dist_dir = DIST_DIR / "NEXORA"
        if dist_dir.exists():
            total = sum(f.stat().st_size for f in dist_dir.rglob("*") if f.is_file())
            print(f"  Directory: {dist_dir}")
            print(f"  Total size: {total / (1024 * 1024):.1f} MB")

    print(f"  Mode: {'single file' if onefile else 'directory'}")
    print(f"  Python: {sys.version.split()[0]}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Build NEXORA standalone app")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts first")
    parser.add_argument("--onefile", action="store_true", help="Build single executable")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend build")
    args = parser.parse_args()

    print("NEXORA Packaging Script")
    print("=" * 40)

    if args.clean:
        clean_build()

    if not args.skip_frontend:
        if not build_frontend():
            sys.exit(1)

    spec_path = create_pyinstaller_spec(args.onefile)

    if not run_pyinstaller(spec_path, args.onefile):
        sys.exit(1)

    create_launcher_script()
    create_desktop_entry()
    create_installer_script()
    print_build_summary(args.onefile)

    print("\nDone!")


if __name__ == "__main__":
    main()
