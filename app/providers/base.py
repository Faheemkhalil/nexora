"""Abstract base provider for AI services."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import AsyncGenerator

from ..core.errors import AuthenticationError, ProviderError


@dataclass
class ProviderConfig:
    id: str
    type: str
    name: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    extra: dict | None = None
    configured: bool = False

    def model_dump(self) -> dict:
        """Convert to dict for JSON serialization."""
        return asdict(self)


@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class ChatResponse:
    content: str
    provider: str
    model: str
    streaming: bool = False


class BaseProvider(ABC):
    """Abstract base class for all AI providers."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @property
    def id(self) -> str:
        return self.config.id

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def configured(self) -> bool:
        return self.config.configured

    @abstractmethod
    async def validate(self) -> bool:
        """Validate provider configuration. Raise on failure."""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = True,
    ) -> AsyncGenerator[ChatResponse, None]:
        """Send chat messages and yield responses (streaming or one-shot)."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up provider resources."""
        ...
