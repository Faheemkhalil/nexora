# NEXORA

**Personal AI Command & Security System**

A futuristic desktop AI assistant combining AI chat, voice interaction, 3D interface, coding workspace, internet research, and defensive cybersecurity tooling.

![NEXORA](https://img.shields.io/badge/Phase-1–8_Complete-brightgreen)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue)
![Three.js](https://img.shields.io/badge/Three.js-WebGL_2.0-cyan)
![Tests](https://img.shields.io/badge/Tests-185_passing-brightgreen)

---

## Features

| Phase | Module | Capabilities |
|-------|--------|-------------|
| 1 | **Foundation** | Desktop shell (pywebview GTK), 3D reactor core (Three.js), backend (aiohttp), WebSocket IPC, SQLite, config, logging |
| 2 | **AI** | Provider abstraction, OpenRouter, custom/local providers, streaming chat, secure API key storage |
| 3 | **Voice** | Push-to-talk, STT (Google/Whisper), TTS (Edge TTS/espeak), voice state visualization |
| 4 | **PC Control** | File read/write/search, system info, integrated terminal, app management, permission system, emergency stop |
| 5 | **Coding** | Code editor with syntax highlighting, git operations, test runner, AI coding agent, project manager |
| 6 | **Internet** | Web search (DuckDuckGo), page fetch with readability extraction, documentation lookup, browser integration |
| 7 | **Security** | Findings management, security lab mode, scope enforcement, report generation (Markdown/HTML/PDF) |
| 8 | **Advanced** | Memory system (global/project/conversation), local AI fallback (Ollama/llama.cpp), enhanced diagnostics |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NEXORA Desktop Shell                      │
│                   (pywebview + GTK WebKit)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Sidebar   │  │ 3D Core  │  │  Chat    │  │  Right   │  │
│  │           │  │ (Three.js│  │ Overlay  │  │  Panel   │  │
│  │           │  │  Reactor)│  │          │  │          │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
├──────────────────── WebSocket IPC ─────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Python Backend (aiohttp)                │   │
│  │                                                     │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │   │
│  │  │ Providers │  │  Voice   │  │  Tool Registry   │ │   │
│  │  │ OpenRouter│  │  STT/TTS │  │  (57 tools)      │ │   │
│  │  │ Custom    │  │  Mic     │  │  files, system   │ │   │
│  │  │ Local     │  │  States  │  │  coding, internet│ │   │
│  │  └──────────┘  └──────────┘  │  security, memory │ │   │
│  │                               └──────────────────┘ │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │   │
│  │  │ Database  │  │ Secrets  │  │  Diagnostics     │ │   │
│  │  │ (SQLite)  │  │ (Keyring)│  │  (10 checks)     │ │   │
│  │  └──────────┘  └──────────┘  └──────────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop Shell | pywebview 6.x (GTK WebKit2GTK) |
| Frontend | TypeScript, Three.js, WebGL 2.0, Vite |
| Backend | Python 3.11+, aiohttp, asyncio |
| Database | SQLite (aiosqlite) |
| AI Providers | OpenRouter, Custom (OpenAI-compatible), Local (Ollama/llama.cpp) |
| Voice | SpeechRecognition, edge-tts, PyAudio/sounddevice |
| Security | findings, lab mode, scope, reports (Markdown/HTML/PDF) |
| Packaging | PyInstaller |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- GTK 3.0 + WebKit2GTK 4.1 (Linux)
- Audio devices (for voice features)

### Install

```bash
# Clone
git clone https://github.com/Faheemkhalil/nexora.git
cd nexora

# Install Python dependencies
pip install -e .

# Install frontend dependencies
cd ui && npm install && npm run build && cd ..
```

### Run

```bash
# Desktop mode (with GUI window)
python3 -m app.main

# Headless mode (backend only, no window)
python3 -m app.main --headless
```

### Run Tests

```bash
# Unit tests
python3 -m pytest tests/unit/ -v

# Integration tests
python3 -m pytest tests/integration/ -v

# All tests
python3 -m pytest tests/ -v
```

### Build Standalone App

```bash
# Build standalone executable
python3 scripts/package.py

# Build single-file executable
python3 scripts/package.py --onefile
```

---

## Project Structure

```
NEXORA/
├── app/                          # Python backend
│   ├── core/                     # Core infrastructure
│   │   ├── config.py             # Pydantic settings
│   │   ├── db.py                 # SQLite + migrations
│   │   ├── diagnostics.py        # System health checks
│   │   ├── errors.py             # Typed error hierarchy
│   │   ├── logging.py            # Structured logging (loguru)
│   │   ├── memory.py             # Scoped memory system
│   │   ├── local_ai.py           # Local AI fallback
│   │   └── secrets.py            # Secure credential storage
│   ├── providers/                # AI provider system
│   │   ├── base.py               # Provider abstraction
│   │   ├── manager.py            # Provider lifecycle
│   │   ├── openrouter.py         # OpenRouter integration
│   │   ├── custom.py             # Custom API endpoint
│   │   └── local.py              # Local inference
│   ├── voice/                    # Voice pipeline
│   │   ├── stt.py                # Speech-to-Text
│   │   ├── tts.py                # Text-to-Speech
│   │   ├── microphone.py         # Audio capture
│   │   └── voice_manager.py      # Pipeline orchestration
│   ├── tools/                    # Tool system
│   │   ├── base.py               # Tool abstraction (57 tools)
│   │   ├── registry.py           # Tool registry + execution
│   │   ├── permissions.py        # Risk levels + emergency stop
│   │   ├── file_tools.py         # File operations
│   │   ├── system_tools.py       # System info
│   │   ├── terminal_tools.py     # Command execution
│   │   └── app_tools.py          # Application management
│   ├── coding/                   # Coding workspace
│   │   ├── code_editor.py        # Read/write/search files
│   │   ├── git_ops.py            # Git operations
│   │   ├── test_runner.py        # Run pytest/npm/cargo
│   │   ├── ai_agent.py           # AI code assistance
│   │   └── project_manager.py    # Project detection
│   ├── internet/                 # Internet tools
│   │   ├── search.py             # Web search
│   │   ├── fetch.py              # Page fetch + JSON API
│   │   ├── docs.py               # Documentation lookup
│   │   └── browser.py            # Browser integration
│   ├── security/                 # Security module
│   │   ├── findings.py           # Finding management
│   │   ├── lab.py                # Lab mode
│   │   ├── reports.py            # Report generation
│   │   └── scope.py              # Scope enforcement
│   ├── ipc.py                    # WebSocket + HTTP IPC
│   └── main.py                   # Entry point
├── ui/                           # TypeScript frontend
│   ├── src/
│   │   ├── app.ts                # Application controller
│   │   ├── scenes/ThreeScene.ts  # 3D reactor core
│   │   ├── components/           # UI components (17)
│   │   ├── screens/              # Settings, Diagnostics
│   │   ├── lib/ipc.ts            # IPC client
│   │   └── styles/main.css       # Global styles
│   └── dist/                     # Built frontend
├── tests/
│   ├── unit/                     # 185 unit tests
│   └── integration/              # End-to-end tests
├── scripts/                      # Build + packaging
│   ├── package.py                # PyInstaller packaging
│   ├── gui_smoke_test.py         # GUI smoke test
│   └── ...
├── pyproject.toml                # Python project config
└── README.md
```

---

## IPC API

All communication between frontend and backend uses WebSocket IPC.

### Connect

```javascript
const ws = new WebSocket('ws://127.0.0.1:8765/ws');
```

### Send Request

```javascript
ws.send(JSON.stringify({
  id: "1",
  method: "chat_stream",
  params: {
    message: "Hello NEXORA",
    conversation_id: null
  }
}));
```

### Available Methods

| Category | Methods |
|----------|---------|
| **Chat** | `chat`, `chat_stream` |
| **Providers** | `providers.list`, `providers.add`, `providers.remove`, `providers.test` |
| **Voice** | `voice.state`, `voice.listen`, `voice.speak`, `voice.stop`, `voice.devices` |
| **Tools** | `tools.list`, `tools.execute`, `tools.confirm`, `tools.cancel` |
| **Coding** | `coding.read_file`, `coding.write_file`, `coding.search`, `coding.git.*`, `coding.test.run`, `coding.agent.*` |
| **Internet** | `internet.search`, `internet.fetch`, `internet.fetch_json`, `internet.docs`, `internet.open` |
| **Security** | `security.findings.*`, `security.lab.*`, `security.reports.generate`, `security.scope.*` |
| **Memory** | `memory.set`, `memory.get`, `memory.search`, `memory.delete`, `memory.clear`, `memory.scopes` |
| **System** | `diagnostics`, `settings.get`, `settings.set`, `shutdown` |

### WebSocket Events

| Event | Description |
|-------|-------------|
| `chat_chunk_start` | Streaming chat response started |
| `chat_chunk` | Streaming text chunk |
| `chat_chunk_end` | Streaming response complete |
| `voice_state` | Voice pipeline state changed |

---

## Settings

Access via the Settings UI or programmatically:

```javascript
// Get settings
const settings = await ipc.request('settings.get');

// Set a setting
await ipc.request('settings.set', {
  key: 'ai.default_temperature',
  value: 0.7
});
```

---

## Security

- **Permission system**: Tools declare risk levels (safe/low/medium/high/critical)
- **Confirmation required**: Destructive operations need explicit user approval
- **Emergency stop**: Global halt for all running operations
- **Scope enforcement**: Security lab tools only operate within authorized scope
- **Audit logging**: All tool executions logged to SQLite
- **Secure storage**: API keys stored via OS keyring, never in plain text

---

## Diagnostics

The built-in diagnostics screen checks:

| Check | What it verifies |
|-------|-----------------|
| Python | Version, interpreter path |
| Platform | OS, architecture |
| Dependencies | All required packages installed |
| Database | SQLite accessible, tables exist |
| Credential storage | Keyring backend available |
| Audio devices | Microphone/speaker detected |
| Provider config | At least one provider configured |
| Internet | Network connectivity |
| Local AI | Ollama/llama.cpp availability |
| Memory | Memory system operational |

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests with coverage
python3 -m pytest tests/ -v --cov=app --cov-report=term-missing

# Type check frontend
cd ui && npx tsc --noEmit

# Build frontend
cd ui && npm run build

# Run GUI smoke test
python3 scripts/gui_smoke_test.py
```

---

## License

Proprietary — NEXORA Development Team
