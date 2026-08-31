"""OpenRouter provider — uses OpenAI-compatible API."""
from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx

from ..core.errors import AuthenticationError, ProviderError
from .base import BaseProvider, ChatMessage, ChatResponse, ProviderConfig

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


class OpenRouterProvider(BaseProvider):
    """AI provider backed by OpenRouter."""

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        if config.base_url:
            self._base_url = config.base_url.rstrip("/")
        else:
            self._base_url = OPENROUTER_API_BASE
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "HTTP-Referer": "https://nexora.local",
                    "X-Title": "NEXORA",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def validate(self) -> bool:
        """Check API key validity by hitting the models endpoint."""
        if not self.config.api_key:
            raise AuthenticationError(
                "No API key configured for OpenRouter.",
                details="Set your OpenRouter API key in Settings.",
            )
        client = self._get_client()
        try:
            resp = await client.get("/models")
            if resp.status_code == 401:
                raise AuthenticationError(
                    "OpenRouter API key is invalid.",
                    details="The server returned 401 Unauthorized.",
                )
            if resp.status_code != 200:
                raise ProviderError(
                    f"OpenRouter validation failed: HTTP {resp.status_code}",
                    details=resp.text[:500],
                )
            data = resp.json()
            if "data" not in data:
                raise ProviderError(
                    "OpenRouter returned unexpected response shape.",
                    details=f"Response keys: {list(data.keys())}",
                )
            return True
        except httpx.HTTPError as e:
            raise ProviderError("Network error during validation.", details=str(e))
        finally:
            await self._cleanup_client()

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = True,
    ) -> AsyncGenerator[ChatResponse, None]:
        """Send a chat request, yielding streaming or one-shot responses."""
        client = self._get_client()

        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        try:
            if stream:
                async with client.stream("POST", "/chat/completions", json=payload) as resp:
                    if resp.status_code == 401:
                        raise AuthenticationError("OpenRouter API key is invalid.")
                    if resp.status_code != 200:
                        text = await resp.aread()
                        raise ProviderError(
                            f"OpenRouter request failed: HTTP {resp.status_code}",
                            details=text.decode()[:500],
                        )
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            chunk = line[6:].strip()
                            if chunk == "[DONE]":
                                break
                            try:
                                data = json.loads(chunk)
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        yield ChatResponse(
                                            content=content,
                                            provider=self.id,
                                            model=self.config.model,
                                            streaming=True,
                                        )
                            except json.JSONDecodeError:
                                continue
            else:
                resp = await client.post("/chat/completions", json=payload)
                if resp.status_code == 401:
                    raise AuthenticationError("OpenRouter API key is invalid.")
                if resp.status_code != 200:
                    raise ProviderError(
                        f"OpenRouter request failed: HTTP {resp.status_code}",
                        details=resp.text[:500],
                    )
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    yield ChatResponse(
                        content=content,
                        provider=self.id,
                        model=self.config.model,
                        streaming=False,
                    )
        except httpx.HTTPError as e:
            raise ProviderError("Network error during chat.", details=str(e))
        finally:
            if not stream:
                await self._cleanup_client()

    async def _cleanup_client(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def close(self) -> None:
        await self._cleanup_client()
