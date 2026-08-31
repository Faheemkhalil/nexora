"""Structured error categories for NEXORA.

Every error in the backend subclasses one of these base categories so the UI
can map them to consistent user-facing messages.
"""
from __future__ import annotations


class NexoraError(Exception):
    """Base class for all NEXORA errors."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} ({self.details})"
        return self.message

    @property
    def category(self) -> str:
        return self.__class__.__name__


class ConfigurationError(NexoraError):
    """Missing or invalid configuration."""


class ProviderError(NexoraError):
    """AI provider returned an error."""


class AuthenticationError(NexoraError):
    """Invalid or missing credentials."""


class NetworkError(NexoraError):
    """Network request failed."""


class ToolError(NexoraError):
    """A tool execution failed."""


class PermissionError(NexoraError):
    """An action requires permission that was denied."""


class ValidationError(NexoraError):
    """Input failed validation."""


class VoiceError(NexoraError):
    """Voice pipeline error."""


class DatabaseError(NexoraError):
    """Database operation failed."""


class SecurityScopeError(NexoraError):
    """Action violated security scope."""


class UIError(NexoraError):
    """UI-layer error."""
