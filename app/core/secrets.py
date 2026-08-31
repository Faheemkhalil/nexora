"""Secure credential storage using the OS keychain.

API keys and tokens are never stored in plain-text config files.
Falls back to local file storage when keyring backend is unavailable.
"""
from __future__ import annotations

import base64
import json
import secrets as _secrets
import string
from pathlib import Path

from .errors import AuthenticationError, ConfigurationError

SERVICE_NAME = "nexora"

# Fallback storage file
_FALLBACK_DIR = Path(__file__).parent.parent.parent / "data"
_FALLBACK_FILE = _FALLBACK_DIR / "secrets.json"

_use_fallback = False


def _init_fallback() -> None:
    """Initialize fallback storage."""
    global _use_fallback
    _FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    if not _FALLBACK_FILE.exists():
        _FALLBACK_FILE.write_text("{}")
        _FALLBACK_FILE.chmod(0o600)
    _use_fallback = True


def _load_fallback() -> dict:
    if not _FALLBACK_FILE.exists():
        return {}
    try:
        data = json.loads(_FALLBACK_FILE.read_text())
        return data
    except Exception:
        return {}


def _save_fallback(data: dict) -> None:
    _FALLBACK_FILE.write_text(json.dumps(data))
    _FALLBACK_FILE.chmod(0o600)


def _try_keyring():
    """Try to use keyring, fall back to file storage if unavailable."""
    global _use_fallback
    if _use_fallback:
        return False
    try:
        import keyring
        kr = keyring.get_keyring()
        # Check if it's a fail backend
        if kr.__class__.__name__ == 'Keyring' and 'fail' in kr.__class__.__module__:
            raise Exception("Fail backend")
        return True
    except Exception:
        _init_fallback()
        return False


def _key_prefix(provider_id: str) -> str:
    return f"nexora.{provider_id}."


def store_api_key(provider_id: str, api_key: str) -> None:
    """Store an API key in the OS keychain or fallback."""
    key = _key_prefix(provider_id) + "api_key"
    if _try_keyring():
        import keyring
        keyring.set_password(SERVICE_NAME, key, api_key)
    else:
        data = _load_fallback()
        data[key] = api_key
        _save_fallback(data)


def retrieve_api_key(provider_id: str) -> str | None:
    """Retrieve an API key from the OS keychain or fallback."""
    key = _key_prefix(provider_id) + "api_key"
    if _try_keyring():
        import keyring
        return keyring.get_password(SERVICE_NAME, key)
    else:
        data = _load_fallback()
        return data.get(key)


def delete_api_key(provider_id: str) -> None:
    """Delete an API key from the OS keychain or fallback."""
    key = _key_prefix(provider_id) + "api_key"
    if _try_keyring():
        import keyring
        keyring.delete_password(SERVICE_NAME, key)
    else:
        data = _load_fallback()
        if key in data:
            del data[key]
            _save_fallback(data)


def has_api_key(provider_id: str) -> bool:
    """Check whether an API key exists without retrieving it."""
    return retrieve_api_key(provider_id) is not None


def generate_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    alphabet = string.ascii_letters + string.digits
    return "".join(_secrets.choice(alphabet) for _ in range(length))


def verify_api_key(provider_id: str) -> str:
    """Retrieve an API key or raise AuthenticationError if missing."""
    key = retrieve_api_key(provider_id)
    if key is None:
        raise AuthenticationError(
            f"No API key stored for provider '{provider_id}'.",
            details="Please configure the API key in Settings before using this provider.",
        )
    return key


def verify_config_value(key: str, value: str | None) -> str:
    """Return the value or raise ConfigurationError if missing."""
    if not value:
        raise ConfigurationError(
            f"Missing required configuration: {key}.",
            details="Please check your configuration or environment variables.",
        )
    return value
