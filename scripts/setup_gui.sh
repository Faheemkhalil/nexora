#!/bin/bash
# NEXORA GUI Setup Script for Kali Linux / Debian
# Installs system packages required for pywebview GTK backend with WebKit2GTK
#
# Usage: sudo ./scripts/setup_gui.sh
#        OR: ./scripts/setup_gui.sh  (will prompt for sudo)

set -euo pipefail

# Colors
GREEN='\033[92m'
RED='\033[91m'
YELLOW='\033[93m'
BLUE='\033[94m'
BOLD='\033[1m'
RESET='\033[0m'

ok() { echo -e "  ${GREEN}✓${RESET} $*"; }
warn() { echo -e "  ${YELLOW}⚠${RESET} $*"; }
fail() { echo -e "  ${RED}✗${RESET} $*"; }
info() { echo -e "  ${BLUE}ℹ${RESET} $*"; }
section() { echo -e "\n${BOLD}$*${RESET}"; echo "----------------------------------------"; }

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    info "Not running as root, will use sudo for package installation"
    SUDO="sudo"
else
    SUDO=""
fi

section "NEXORA GUI Setup for Kali Linux / Debian"

# Detect distribution
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    info "Distribution: $PRETTY_NAME"
    info "Version: $VERSION_ID"
fi

# Check current display
section "Display Environment"
if [[ -n "${DISPLAY:-}" ]]; then
    ok "DISPLAY=$DISPLAY"
else
    warn "DISPLAY not set - GUI apps won't work without X11/Wayland"
fi

if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    ok "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
else
    info "WAYLAND_DISPLAY not set (X11 assumed)"
fi

# Required packages for pywebview GTK backend
# pywebview 6.x requires:
# - gir1.2-webkit2-4.1 (GObject introspection for WebKit2 4.1)
# - libwebkit2gtk-4.1-0 (runtime)
# - python3-gi (Python GObject bindings)
# - python3-gi-cairo (Cairo bindings)
PACKAGES=(
    "gir1.2-webkit2-4.1"
    "libwebkit2gtk-4.1-0"
    "python3-gi"
    "python3-gi-cairo"
)

# Optional but recommended
OPTIONAL_PACKAGES=(
    "libwebkit2gtk-4.1-dev"
    "xvfb"
    "x11-utils"
)

section "Checking currently installed packages"

MISSING_REQUIRED=()
MISSING_OPTIONAL=()

for pkg in "${PACKAGES[@]}"; do
    if dpkg -l "$pkg" 2>/dev/null | grep -q '^ii'; then
        ok "$pkg already installed"
    else
        fail "$pkg NOT installed"
        MISSING_REQUIRED+=("$pkg")
    fi
done

for pkg in "${OPTIONAL_PACKAGES[@]}"; do
    if dpkg -l "$pkg" 2>/dev/null | grep -q '^ii'; then
        ok "$pkg already installed"
    else
        warn "$pkg NOT installed (optional)"
        MISSING_OPTIONAL+=("$pkg")
    fi
done

if [[ ${#MISSING_REQUIRED[@]} -eq 0 && ${#MISSING_OPTIONAL[@]} -eq 0 ]]; then
    ok "All packages already installed!"
    exit 0
fi

section "Package Installation"

# Update package list
info "Updating package list..."
$SUDO apt-get update

# Install required packages
if [[ ${#MISSING_REQUIRED[@]} -gt 0 ]]; then
    info "Installing required packages: ${MISSING_REQUIRED[*]}"
    $SUDO apt-get install -y "${MISSING_REQUIRED[@]}"
    ok "Required packages installed"
fi

# Install optional packages
if [[ ${#MISSING_OPTIONAL[@]} -gt 0 ]]; then
    info "Installing optional packages: ${MISSING_OPTIONAL[*]}"
    $SUDO apt-get install -y "${MISSING_OPTIONAL[@]}"
    ok "Optional packages installed"
fi

section "Verifying Installation"

# Verify Python GI bindings work
info "Testing Python GI bindings..."
if python3 -c "import gi; gi.require_version('WebKit2', '4.1'); from gi.repository import WebKit2; print('WebKit2 4.1 OK')" 2>/dev/null; then
    ok "WebKit2 4.1 Python bindings working"
else
    fail "WebKit2 4.1 Python bindings NOT working"
    exit 1
fi

if python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk; print('GTK 3.0 OK')" 2>/dev/null; then
    ok "GTK 3.0 Python bindings working"
elif python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk; print('GTK 4.0 OK')" 2>/dev/null; then
    ok "GTK 4.0 Python bindings working"
else
    fail "No GTK Python bindings working"
    exit 1
fi

# Verify pywebview can initialize
info "Testing pywebview GTK backend..."
if python3 -c "import webview; webview.initialize('gtk'); assert webview.guilib is not None; print(f'Backend: {webview.guilib.__name__}')" 2>/dev/null; then
    ok "pywebview GTK backend initialized successfully"
else
    fail "pywebview GTK backend failed to initialize"
    exit 1
fi

section "Setup Complete!"
ok "All system dependencies for NEXORA GUI are installed."
info "Next steps:"
echo "  1. cd /home/faheemkhalil/NEXORA"
echo "  2. python3 -m pip install -e ."
echo "  3. cd ui && npm install && npm run build"
echo "  4. python3 -m app.main"
echo ""
info "Or run the diagnostic: python3 scripts/check_gui.py"
info "Or run the smoke test: python3 scripts/gui_smoke_test.py"