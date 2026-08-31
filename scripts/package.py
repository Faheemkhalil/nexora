#!/usr/bin/env python3
"""NEXORA — Packaging Script

Builds NEXORA as a standalone desktop application using PyInstaller.

Usage:
    python3 scripts/package.py              # Build for current platform
    python3 scripts/package.py --clean       # Clean build artifacts first
    python3 scripts/package.py --onefile      # Single executable (slower startup)
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
    print("🔨 Building frontend...")
    ui_dir = PROJECT_ROOT / "ui"
    if not (ui_dir / "package.json").exists():
        print("  ⚠ No ui/package.json found, skipping frontend build")
        return True

    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=ui_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ✗ Frontend build failed:\n{result.stderr}")
        return False

    print("  ✓ Frontend built successfully")
    return True


def clean() -> None:
    """Clean build artifacts."""
    print("🧹 Cleaning build artifacts...")
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  Removed {d}")
    print("  ✓ Clean")


def create_pyinstaller_spec(onefile: bool = False) -> Path:
    """Generate the PyInstaller spec file."""
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
"""NEXORA PyInstaller Spec"""

import os
from pathlib import Path

block_cipher = None
project_root = Path('{PROJECT_ROOT}')
ui_dist = project_root / 'ui' / 'dist'

a = Analysis(
    [str(project_root / 'app' / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(ui_dist), 'ui/dist') if ui_dist.exists() else None,
        (str(project_root / 'data'), 'data') if (project_root / 'data').exists() else None,
    ],
    hiddenimports=[
        'app',
        'app.core',
        'app.core.config',
        'app.core.db',
        'app.core.diagnostics',
        'app.core.errors',
        'app.core.logging',
        'app.core.memory',
        'app.core.secrets',
        'app.core.local_ai',
        'app.providers',
        'app.providers.base',
        'app.providers.manager',
        'app.providers.openrouter',
        'app.providers.custom',
        'app.providers.local',
        'app.voice',
        'app.voice.stt',
        'app.voice.tts',
        'app.voice.microphone',
        'app.voice.voice_manager',
        'app.tools',
        'app.tools.base',
        'app.tools.registry',
        'app.tools.permissions',
        'app.tools.file_tools',
        'app.tools.system_tools',
        'app.tools.terminal_tools',
        'app.tools.app_tools',
        'app.coding',
        'app.coding.code_editor',
        'app.coding.git_ops',
        'app.coding.test_runner',
        'app.coding.ai_agent',
        'app.coding.project_manager',
        'app.internet',
        'app.internet.search',
        'app.internet.fetch',
        'app.internet.docs',
        'app.internet.browser',
        'app.security',
        'app.security.findings',
        'app.security.lab',
        'app.security.reports',
        'app.security.scope',
        'app.ipc',
        'aiohttp',
        'aiosqlite',
        'pydantic',
        'pydantic_settings',
        'loguru',
        'httpx',
        'webview',
        'webview.platforms.gtk',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

{'exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [], name="NEXORA", debug=False, bootloader_ignore_signals=False, strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None, console=False, disable_windowed_traceback=False, argv_emulation=False, target_arch=None, codesign_identity=None, entitlements_file=None)' if onelone else 'exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NEXORA", debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False, disable_windowed_traceback=False)'}

{'coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, upx_exclude=[], name="NEXORA")' if not onelone else ''}
"""

    spec_path = PROJECT_ROOT / "nexora.spec"
    spec_path.write_text(spec_content)
    print(f"  ✓ Spec file: {spec_path}")
    return spec_path


def run_pyinstaller(spec_path: Path, onefile: bool = False) -> bool:
    """Run PyInstaller."""
    print("📦 Building standalone app with PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", "NEXORA",
        "--windowed",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
    ]

    if not onefile:
        cmd.append("--onedir")

    cmd.append(str(spec_path))

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"  ✗ PyInstaller failed:\n{result.stderr[-2000:]}")
        return False

    print("  ✓ Build complete")
    return True


def create_launcher_script() -> None:
    """Create a cross-platform launcher script."""
    launcher = DIST_DIR / "NEXORA" / "NEXORA"
    if launcher.exists():
        launcher.chmod(0o755)
        print(f"  ✓ Launcher: {launcher}")


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
    print(f"  ✓ Desktop entry: {desktop_path}")


def create_installer_script() -> None:
    """Create a simple install/uninstall script."""
    install_script = DIST_DIR / "NEXORA" / "install.sh"
    install_script.write_text(f"""#!/bin/bash
# NEXORA Installer
# Run this script to install NEXORA system-wide

INSTALL_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/nexora"

echo "Installing NEXORA..."

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$APP_DIR"

# Copy files
cp -r "$(dirname "$0")"/* "$APP_DIR/"

# Create symlink
ln -sf "$APP_DIR/NEXORA" "$INSTALL_DIR/nexora"

# Make executable
chmod +x "$APP_DIR/NEXORA"

echo "NEXORA installed to $APP_DIR"
echo "Run 'nexora' from terminal or find it in your applications menu."
echo ""
echo "To uninstall:"
echo "  rm -rf $APP_DIR"
echo "  rm -f $INSTALL_DIR/nexora"
""")
    install_script.chmod(0o755)
    print(f"  ✓ Installer: {install_script}")


def print_summary() -> None:
    """Print build summary."""
    print("\n" + "=" * 60)
    print("NEXORA Build Summary")
    print("=" * 60)

    if DIST_DIR.exists():
        app_dir = DIST_DIR / "NEXORA"
        if app_dir.exists():
            total_size = sum(f.stat().st_size for f in app_dir.rglob("*") if f.is_file())
            print(f"  Output: {app_dir}")
            print(f"  Size: {total_size / (1024 * 1024):.1f} MB")
            exe = app_dir / "NEXORA"
            if exe.exists():
                print(f"  Run: {exe}")
            desktop = app_dir / "nexora.desktop"
            if desktop.exists():
                print(f"  Desktop entry: {desktop}")
        else:
            exe_file = DIST_DIR / "NEXORA"
            if exe_file.exists():
                print(f"  Output: {exe_file}")
                print(f"  Size: {exe_file.stat().st_size / (1024 * 1024):.1f} MB")
                print(f"  Run: {exe_file}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Package NEXORA as standalone app")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts first")
    parser.add_argument("--onefile", action="store_true", help="Build single executable")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend build")
    args = parser.parse_args()

    print("NEXORA Packaging Script")
    print("=" * 40)

    if args.clean:
        clean()

    # 1. Build frontend
    if not args.skip_frontend:
        if not build_frontend():
            sys.exit(1)

    # 2. Generate spec
    spec_path = create_pyinstaller_spec(onefile=args.onefile)

    # 3. Run PyInstaller
    if not run_pyinstaller(spec_path, onefile=args.onefile):
        sys.exit(1)

    # 4. Post-build
    create_launcher_script()
    create_desktop_entry()
    create_installer_script()

    # 5. Summary
    print_summary()


if __name__ == "__main__":
    main()
