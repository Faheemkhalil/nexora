# NEXORA — Personal AI Command & Security System

A futuristic desktop AI assistant with a 3D command-center interface.

## Architecture

- **Frontend**: TypeScript + Three.js, served by an embedded HTTP server
- **Desktop Shell**: Python backend with `pywebview` hosting a native window
- **IPC**: WebSocket transport between the web UI and Python backend
- **Database**: SQLite with async access via `aiosqlite`
- **Providers**: Pluggable AI provider abstraction (OpenRouter, custom, local)
- **Secrets**: OS keychain via `keyring` for API keys

---

## Quick Start (Development)

```bash
# 1. Install system dependencies (requires sudo)
sudo ./scripts/setup_gui.sh

# 2. Install Python package in development mode
pip3 install -e ".[dev]"

# 3. Build frontend assets
cd ui && npm install && npm run build
cd ..

# 4. Run NEXORA
python3 -m app.main
```

---

## GUI Environment Setup

### System Requirements

- **Display**: X11 (DISPLAY) or Wayland (WAYLAND_DISPLAY)
- **Python**: 3.11+
- **System packages** (Debian/Kali):
  - `gir1.2-webkit2-4.1` — WebKit2GTK GObject introspection (**REQUIRED**)
  - `libwebkit2gtk-4.1-0` — WebKit2GTK runtime
  - `python3-gi` — Python GObject bindings
  - `python3-gi-cairo` — Python Cairo bindings
  - `xvfb` — Virtual framebuffer (for headless/CI testing)

### Automated Setup

```bash
# Run the setup script (prompts for sudo if needed)
./scripts/setup_gui.sh
```

This script:
1. Detects your display environment (X11/Wayland)
2. Checks currently installed packages
3. Installs missing required/optional packages via apt
4. Verifies Python GI bindings work
5. Verifies pywebview GTK backend initializes

### Manual Verification

```bash
# Run full environment diagnostic
python3 scripts/check_gui.py

# Expected output: All checks PASS
# If any FAIL, fix before proceeding
```

---

## Frontend Build

The frontend uses Vite + TypeScript + Three.js (via CDN importmap).

```bash
cd ui

# Install dependencies
npm install

# Development server (with hot reload)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

cd ..
```

**Build output**: `ui/dist/` (served as `/webui/` by the backend)

**Note**: Three.js is loaded from CDN via importmap in `index.html` — works offline after first load due to browser caching.

---

## Launching NEXORA

### Desktop Mode (GUI)

```bash
# From project root
python3 -m app.main
```

This starts:
1. Backend (database, providers, IPC server on `ws://127.0.0.1:8765/ws`)
2. Native desktop window via pywebview (GTK+WebKit2)
3. Loads UI from `http://127.0.0.1:8765/webui/`

### Headless Mode (Backend Only)

```bash
python3 -m app.main --headless
```

Useful for:
- Server deployments
- API-only usage
- CI/CD pipelines

---

## Running Tests

### Backend Unit Tests

```bash
# All tests
python3 -m pytest tests/ -v

# Specific test file
python3 -m pytest tests/unit/test_config.py -v
```

### GUI Smoke Test

**Requires graphical environment** (or xvfb):

```bash
# On graphical desktop
python3 scripts/gui_smoke_test.py

# On headless/CI with xvfb
xvfb-run -a python3 scripts/gui_smoke_test.py
```

Tests performed:
1. Module imports (pywebview, app.main, app.ipc)
2. Backend startup & IPC server
3. HTTP endpoints (/healthz, /api/providers, /api/diagnostics, /api/conversations, static files)
4. WebSocket IPC (ping, providers.list, diagnostics)
5. **GUI window creation** (actual native window)
6. Clean shutdown

---

## Troubleshooting

### "pywebview GTK cannot be loaded"

```bash
# Missing WebKit2GTK GI bindings
sudo apt-get install gir1.2-webkit2-4.1 python3-gi python3-gi-cairo

# Verify
python3 -c "import gi; gi.require_version('WebKit2', '4.1'); from gi.repository import WebKit2; print('OK')"
```

### "No module named 'qtpy'" / QT backend errors

The project uses GTK backend. QT is not required. If pywebview tries QT, ensure GTK is initialized first:

```python
import webview
webview.initialize('gtk')  # Must be called before create_window
```

### "Cannot open display" / DISPLAY issues

```bash
# Check display
echo $DISPLAY

# If using SSH, enable X11 forwarding
ssh -X user@host

# For headless testing
xvfb-run -a python3 scripts/gui_smoke_test.py
```

### Frontend not loading / 404 on static files

```bash
# Rebuild frontend
cd ui && npm run build && cd ..

# Verify files exist
ls -la ui/dist/
ls -la ui/src/
```

### WebSocket connection failed

```bash
# Check backend is running
curl http://127.0.0.1:8765/healthz

# Check port
ss -tlnp | grep 8765
```

### Backend exceptions on startup

```bash
# Run with debug logging
LOGURU_LEVEL=DEBUG python3 -m app.main --headless
```

---

## Project Structure

```
NEXORA/
├── app/
│   ├── core/           # Config, DB, logging, secrets, errors, diagnostics
│   ├── providers/      # AI provider abstraction + implementations
│   ├── ipc.py          # HTTP + WebSocket server + static file serving
│   └── main.py         # Application entry point (desktop + headless)
├── ui/
│   ├── src/            # TypeScript source
│   │   ├── components/ # Sidebar, ChatOverlay, RightPanel, StatusBar
│   │   ├── screens/    # SettingsModal, DiagnosticsModal
│   │   ├── scenes/     # ThreeScene (3D AI core)
│   │   ├── lib/        # IPCClient
│   │   ├── app.ts      # Main app controller
│   │   └── main.ts     # Entry point
│   ├── styles/         # CSS (main.css)
│   ├── index.html      # HTML entry (served as /webui/)
│   └── package.json    # Frontend build config
├── scripts/
│   ├── check_gui.py    # Environment diagnostic
│   ├── gui_smoke_test.py # GUI smoke test
│   └── setup_gui.sh    # System package installer
├── tests/
│   └── unit/           # 48 unit tests
├── data/               # Runtime data (DB, logs)
├── pyproject.toml      # Python package config
└── README.md
```

---

## Configuration

Settings are managed via Pydantic Settings in `app/core/config.py` with environment variable overrides:

| Setting | Env Var | Default |
|---------|---------|---------|
| Database path | `NEXORA_DB_PATH` | `~/.nexora/nexora.db` |
| Server host | `NEXORA_SERVER_HOST` | `127.0.0.1` |
| Server port | `NEXORA_SERVER_PORT` | `8765` |
| UI fullscreen | `NEXORA_UI_FULLSCREEN` | `false` |
| Log level | `NEXORA_LOG_LEVEL` | `INFO` |

---

## Provider Setup

1. Open **Settings** → **Providers** tab
2. Click **Add Provider**
3. Select type:
   - **OpenRouter** — Enter API key, model (e.g., `openai/gpt-4`)
   - **Custom** — OpenAI-compatible endpoint + API key
   - **Local** — Ollama/llama.cpp base URL (no API key needed)
4. Click **Save**
5. Test connection with **Test** button

---

## Development

### Adding a New Provider

1. Create `app/providers/yourprovider.py` extending `BaseProvider`
2. Register in `app/providers/__init__.py`
3. Add to `ProviderType` enum in `app/providers/base.py`

### Running Diagnostics

```bash
# Via IPC (when backend running)
curl http://127.0.0.1:8765/api/diagnostics

# Or from UI: Settings → Diagnostics → Run Again
```

### Database Migrations

Migrations run automatically on startup. Schema version tracked in `.schema_version` file alongside DB.

---

## License

Proprietary — NEXORA Development Team