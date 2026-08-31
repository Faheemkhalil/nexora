"""Unit tests for secrets module."""
import pytest
import tempfile
from pathlib import Path

from app.core import secrets


@pytest.fixture
def temp_secrets_dir():
    """Use a temporary directory for fallback storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_dir = secrets._FALLBACK_DIR
        original_file = secrets._FALLBACK_FILE
        original_fallback = secrets._use_fallback

        secrets._FALLBACK_DIR = Path(tmpdir)
        secrets._FALLBACK_FILE = Path(tmpdir) / "secrets.json"
        secrets._use_fallback = False

        yield tmpdir

        # Restore
        secrets._FALLBACK_DIR = original_dir
        secrets._FALLBACK_FILE = original_file
        secrets._use_fallback = original_fallback


def test_store_and_retrieve_api_key(temp_secrets_dir):
    """Test storing and retrieving an API key."""
    provider_id = "test-provider"
    api_key = "sk-test12345"

    secrets.store_api_key(provider_id, api_key)
    retrieved = secrets.retrieve_api_key(provider_id)

    assert retrieved == api_key


def test_delete_api_key(temp_secrets_dir):
    """Test deleting an API key."""
    provider_id = "test-provider"
    api_key = "sk-test12345"

    secrets.store_api_key(provider_id, api_key)
    assert secrets.has_api_key(provider_id)

    secrets.delete_api_key(provider_id)
    assert not secrets.has_api_key(provider_id)
    assert secrets.retrieve_api_key(provider_id) is None


def test_has_api_key(temp_secrets_dir):
    """Test checking for API key existence."""
    provider_id = "test-provider"

    assert not secrets.has_api_key(provider_id)

    secrets.store_api_key(provider_id, "key")
    assert secrets.has_api_key(provider_id)


def test_verify_api_key_raises(temp_secrets_dir):
    """Test verify_api_key raises on missing key."""
    with pytest.raises(secrets.AuthenticationError):
        secrets.verify_api_key("nonexistent")


def test_verify_api_key_returns_key(temp_secrets_dir):
    """Test verify_api_key returns key when present."""
    provider_id = "test-provider"
    api_key = "sk-test12345"

    secrets.store_api_key(provider_id, api_key)
    result = secrets.verify_api_key(provider_id)

    assert result == api_key


def test_verify_config_value():
    """Test verify_config_value."""
    assert secrets.verify_config_value("test", "value") == "value"

    with pytest.raises(secrets.ConfigurationError):
        secrets.verify_config_value("test", None)

    with pytest.raises(secrets.ConfigurationError):
        secrets.verify_config_value("test", "")


def test_generate_token():
    """Test token generation."""
    token = secrets.generate_token(32)
    assert len(token) == 32
    assert token.isalnum()

    token2 = secrets.generate_token(16)
    assert len(token2) == 16
    assert token != token2


def test_multiple_providers_isolated(temp_secrets_dir):
    """Test keys for different providers are isolated."""
    secrets.store_api_key("provider1", "key1")
    secrets.store_api_key("provider2", "key2")

    assert secrets.retrieve_api_key("provider1") == "key1"
    assert secrets.retrieve_api_key("provider2") == "key2"

    secrets.delete_api_key("provider1")
    assert not secrets.has_api_key("provider1")
    assert secrets.has_api_key("provider2")