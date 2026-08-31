"""Unit tests for provider abstraction."""
import pytest
import asyncio
from dataclasses import asdict

from app.providers.base import ProviderConfig, ChatMessage, ChatResponse, BaseProvider


def test_provider_config_creation():
    """Test ProviderConfig creation."""
    config = ProviderConfig(
        id="test",
        type="openrouter",
        name="Test",
        model="gpt-4",
        api_key="key",
        base_url="https://api.example.com",
        extra={"foo": "bar"},
        configured=True,
    )
    assert config.id == "test"
    assert config.type == "openrouter"
    assert config.configured is True


def test_provider_config_model_dump():
    """Test ProviderConfig.model_dump()."""
    config = ProviderConfig(
        id="test",
        type="openrouter",
        name="Test",
        model="gpt-4",
    )
    dumped = config.model_dump()
    assert dumped["id"] == "test"
    assert dumped["type"] == "openrouter"
    assert dumped["name"] == "Test"
    assert dumped["model"] == "gpt-4"
    assert dumped["api_key"] is None
    assert dumped["base_url"] is None
    assert dumped["extra"] is None
    assert dumped["configured"] is False


def test_chat_message():
    """Test ChatMessage dataclass."""
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_chat_response():
    """Test ChatResponse dataclass."""
    resp = ChatResponse(
        content="Hello there!",
        provider="test",
        model="gpt-4",
        streaming=True,
    )
    assert resp.content == "Hello there!"
    assert resp.provider == "test"
    assert resp.model == "gpt-4"
    assert resp.streaming is True


class MockProvider(BaseProvider):
    """Mock provider for testing."""

    async def validate(self) -> bool:
        return True

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = True,
    ):
        yield ChatResponse(
            content="Mock response",
            provider=self.id,
            model=self.model,
            streaming=stream,
        )

    async def close(self) -> None:
        pass


def test_base_provider_properties():
    """Test BaseProvider properties."""
    config = ProviderConfig(
        id="mock",
        type="mock",
        name="Mock",
        model="mock-model",
        configured=True,
    )
    provider = MockProvider(config)

    assert provider.id == "mock"
    assert provider.name == "Mock"
    assert provider.model == "mock-model"
    assert provider.configured is True


def test_mock_provider_chat():
    """Test MockProvider chat method."""
    config = ProviderConfig(
        id="mock",
        type="mock",
        name="Mock",
        model="mock-model",
        configured=True,
    )
    provider = MockProvider(config)

    messages = [ChatMessage(role="user", content="Test")]
    responses = []
    async def run():
        async for resp in provider.chat(messages, stream=True):
            responses.append(resp)
    asyncio.run(run())

    assert len(responses) == 1
    assert responses[0].content == "Mock response"
    assert responses[0].streaming is True
    assert responses[0].provider == "mock"


def test_mock_provider_chat_non_streaming():
    """Test MockProvider chat non-streaming."""
    config = ProviderConfig(
        id="mock",
        type="mock",
        name="Mock",
        model="mock-model",
        configured=True,
    )
    provider = MockProvider(config)

    messages = [ChatMessage(role="user", content="Test")]
    responses = []
    async def run():
        async for resp in provider.chat(messages, stream=False):
            responses.append(resp)
    asyncio.run(run())

    assert len(responses) == 1
    assert responses[0].streaming is False