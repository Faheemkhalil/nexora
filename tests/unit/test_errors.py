"""Unit tests for error taxonomy."""
import pytest

from app.core.errors import (
    NexoraError,
    ConfigurationError,
    ProviderError,
    AuthenticationError,
    NetworkError,
    ToolError,
    PermissionError,
    ValidationError,
    VoiceError,
    DatabaseError,
    SecurityScopeError,
    UIError,
)


def test_nexora_error_base():
    """Test base NexoraError."""
    e = NexoraError("test message", details="details")
    assert str(e) == "test message (details)"
    assert e.category == "NexoraError"
    assert e.details == "details"


def test_nexora_error_no_details():
    """Test NexoraError without details."""
    e = NexoraError("test message")
    assert str(e) == "test message"
    assert e.details is None


def test_configuration_error():
    """Test ConfigurationError."""
    e = ConfigurationError("config missing")
    assert e.category == "ConfigurationError"


def test_provider_error():
    """Test ProviderError."""
    e = ProviderError("provider failed")
    assert e.category == "ProviderError"


def test_authentication_error():
    """Test AuthenticationError."""
    e = AuthenticationError("auth failed", details="no key")
    assert e.category == "AuthenticationError"
    assert e.details == "no key"


def test_network_error():
    """Test NetworkError."""
    e = NetworkError("connection failed")
    assert e.category == "NetworkError"


def test_tool_error():
    """Test ToolError."""
    e = ToolError("tool failed")
    assert e.category == "ToolError"


def test_permission_error():
    """Test PermissionError."""
    e = PermissionError("not allowed")
    assert e.category == "PermissionError"


def test_validation_error():
    """Test ValidationError."""
    e = ValidationError("invalid input")
    assert e.category == "ValidationError"


def test_voice_error():
    """Test VoiceError."""
    e = VoiceError("mic failed")
    assert e.category == "VoiceError"


def test_database_error():
    """Test DatabaseError."""
    e = DatabaseError("db failed")
    assert e.category == "DatabaseError"


def test_security_scope_error():
    """Test SecurityScopeError."""
    e = SecurityScopeError("scope violation")
    assert e.category == "SecurityScopeError"


def test_ui_error():
    """Test UIError."""
    e = UIError("ui error")
    assert e.category == "UIError"


def test_error_inheritance():
    """Test all errors inherit from NexoraError."""
    errors = [
        ConfigurationError(""),
        ProviderError(""),
        AuthenticationError(""),
        NetworkError(""),
        ToolError(""),
        PermissionError(""),
        ValidationError(""),
        VoiceError(""),
        DatabaseError(""),
        SecurityScopeError(""),
        UIError(""),
    ]
    for e in errors:
        assert isinstance(e, NexoraError)