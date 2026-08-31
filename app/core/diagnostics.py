"""Self-diagnostics for the NEXORA system.

Each check returns a dict with: name, status (ok/warning/error), details, remediation.
"""
from __future__ import annotations

import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from .config import settings
from .errors import DatabaseError

try:
    import aiosqlite
    _HAS_AIOSQLITE = True
except ImportError:
    _HAS_AIOSQLITE = False

try:
    import keyring
    _HAS_KEYRING = True
except ImportError:
    _HAS_KEYRING = False

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

try:
    import pyaudio
    _HAS_PYAUDIO = True
except ImportError:
    _HAS_PYAUDIO = False

try:
    import pywebview
    _HAS_WEBVIEW = True
except ImportError:
    _HAS_WEBVIEW = False


@dataclass
class DiagnosticResult:
    name: str
    status: str  # "ok", "warning", "error"
    details: str
    remediation: str | None = None


STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_ERROR = "error"


async def _check_database() -> DiagnosticResult:
    db_path = settings.database.path
    if not db_path.parent.exists():
        return DiagnosticResult(
            "Database directory",
            STATUS_WARNING,
            f"Database directory {db_path.parent} does not exist; will be created on startup.",
            "No action needed — this is normal for a fresh install.",
        )
    if db_path.exists():
        try:
            import aiosqlite

            async with aiosqlite.connect(str(db_path)) as db:
                async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
                    tables = await cur.fetchall()
            return DiagnosticResult(
                "Database",
                STATUS_OK,
                f"Database at {db_path} is accessible. {len(tables)} table(s) present.",
            )
        except Exception as e:
            return DiagnosticResult(
                "Database",
                STATUS_ERROR,
                f"Database at {db_path} exists but is not accessible.",
                details=str(e),
            )
    else:
        return DiagnosticResult(
            "Database",
            STATUS_WARNING,
            f"Database file at {db_path} does not exist yet.",
            "It will be created automatically on first startup.",
        )


async def _check_python() -> DiagnosticResult:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        status = STATUS_OK
    else:
        status = STATUS_ERROR
    return DiagnosticResult(
        "Python",
        status,
        f"Python {version} — {'OK' if status == STATUS_OK else 'Too old, min 3.11'}",
        None if status == STATUS_OK else "Upgrade to Python 3.11 or newer.",
    )


async def _check_provider_config() -> DiagnosticResult:
    try:
        from app.providers import manager as provider_manager

        providers = provider_manager.list_providers()
        if not providers:
            return DiagnosticResult(
                "Provider configuration",
                STATUS_WARNING,
                "No AI providers configured.",
                "Add an OpenRouter key or configure a custom/local provider in Settings.",
            )
        configured = [p for p in providers if p.configured]
        if not configured:
            return DiagnosticResult(
                "Provider configuration",
                STATUS_WARNING,
                f"{len(providers)} provider(s) exist but none are configured with credentials.",
                "Configure an API key in Settings or enable a local provider.",
            )
        return DiagnosticResult(
            "Provider configuration",
            STATUS_OK,
            f"{len(configured)} configurable provider(s): " + ", ".join(p.name for p in configured) + ".",
        )
    except Exception as e:
        return DiagnosticResult(
            "Provider configuration",
            STATUS_ERROR,
            f"Failed to read provider configuration: {e}",
            "Check the application logs.",
        )


async def _check_dependencies() -> DiagnosticResult:
    missing: list[str] = []
    for name, available in [
        ("aiosqlite", _HAS_AIOSQLITE),
        ("keyring", _HAS_KEYRING),
        ("httpx", _HAS_HTTPX),
        ("pywebview", _HAS_WEBVIEW),
    ]:
        if not available:
            missing.append(name)

    if not missing:
        return DiagnosticResult(
            "Core dependencies",
            STATUS_OK,
            "All core Python dependencies are installed.",
        )
    return DiagnosticResult(
        "Core dependencies",
        STATUS_ERROR,
        f"Missing dependencies: {', '.join(missing)}",
        "Install with: pip install -e \".[dev]\"",
    )


async def _check_audio() -> DiagnosticResult:
    if _HAS_PYAUDIO:
        try:
            import pyaudio

            pa = pyaudio.PyAudio()
            device_count = pa.get_device_count()
            pa.terminate()
            if device_count > 0:
                return DiagnosticResult(
                    "Audio devices",
                    STATUS_OK,
                    f"Audio subsystem available. {device_count} device(s) detected.",
                )
            return DiagnosticResult(
                "Audio devices",
                STATUS_WARNING,
                "pyaudio is installed but no audio devices found.",
                "Voice features will be unavailable.",
            )
        except Exception as e:
            return DiagnosticResult(
                "Audio devices",
                STATUS_ERROR,
                f"pyaudio installed but audio initialization failed: {e}",
                "Check microphone/permissions.",
            )
    return DiagnosticResult(
        "Audio devices",
        STATUS_WARNING,
        "pyaudio is not installed.",
        "Voice input/output will be unavailable. Install with: pip install pyaudio",
    )


async def _check_platform() -> DiagnosticResult:
    gpu_available = "unknown"
    renderer = platform.platform()
    return DiagnosticResult(
        "Platform",
        STATUS_OK,
        f"OS: {renderer}, Python: {sys.version.split()[0]}, "
        f"Machine: {platform.machine()}, GPU: {gpu_available}",
        None,
    )


async def _check_keyring() -> DiagnosticResult:
    if not _HAS_KEYRING:
        return DiagnosticResult(
            "Credential storage",
            STATUS_ERROR,
            "keyring package not installed.",
            "Install with: pip install keyring",
        )

    backend_name = type(keyring.get_keyring()).__name__
    if backend_name in ("NullKeyring", "fail.Keyring"):
        return DiagnosticResult(
            "Credential storage",
            STATUS_WARNING,
            f"keyring backend is '{backend_name}' — credentials will not be persistently stored.",
            "On Linux, install a backend like secretstorage: pip install secretstorage",
        )
    return DiagnosticResult(
        "Credential storage",
        STATUS_OK,
        f"keyring backend: {backend_name}. API keys will be stored securely.",
    )


async def _check_internet() -> DiagnosticResult:
    """Check internet connectivity."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("https://httpbin.org/ip")
            if resp.status_code == 200:
                return DiagnosticResult("Internet connectivity", STATUS_OK, "Internet connection available.")
    except Exception:
        pass
    return DiagnosticResult(
        "Internet connectivity",
        STATUS_WARNING,
        "Internet not available. Online features will be limited.",
        "Check your network connection.",
    )


async def _check_local_ai() -> DiagnosticResult:
    """Check for local AI backends (Ollama, llama.cpp)."""
    from .local_ai import detect_local_ai
    info = await detect_local_ai()
    if info:
        models = info.get("models", [])
        return DiagnosticResult(
            "Local AI",
            STATUS_OK,
            f"{info['backend']} detected: {len(models)} model(s) available.",
        )
    return DiagnosticResult(
        "Local AI",
        STATUS_WARNING,
        "No local AI backend detected (Ollama, llama.cpp).",
        "Install Ollama (https://ollama.com) for offline AI capabilities.",
    )


async def _check_memory_system() -> DiagnosticResult:
    """Check the memory system."""
    try:
        from .memory import memory
        scopes = await memory.list_scopes()
        total = sum(s["count"] for s in scopes)
        return DiagnosticResult(
            "Memory system",
            STATUS_OK,
            f"Memory operational. {total} entries across {len(scopes)} scope(s).",
        )
    except Exception as e:
        return DiagnosticResult(
            "Memory system",
            STATUS_ERROR,
            f"Memory system error: {e}",
            "Check database and logs.",
        )


async def run_all_diagnostics() -> list[DiagnosticResult]:
    """Run all diagnostic checks and return results."""
    logger.info("Running diagnostics...")
    checks = [
        _check_python,
        _check_platform,
        _check_dependencies,
        _check_database,
        _check_keyring,
        _check_audio,
        _check_provider_config,
        _check_internet,
        _check_local_ai,
        _check_memory_system,
    ]
    results: list[DiagnosticResult] = []
    for check in checks:
        try:
            result = await check()
            results.append(result)
        except Exception as e:
            results.append(
                DiagnosticResult(
                    check.__name__,
                    STATUS_ERROR,
                    f"Diagnostic check failed: {e}",
                    "Check the application logs.",
                )
            )

    ok = sum(1 for r in results if r.status == STATUS_OK)
    warn = sum(1 for r in results if r.status == STATUS_WARNING)
    err = sum(1 for r in results if r.status == STATUS_ERROR)
    logger.info(f"Diagnostics complete: {ok} OK, {warn} warnings, {err} errors.")
    return results
