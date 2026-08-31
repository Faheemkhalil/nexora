"""Custom provider — OpenAI-compatible API at a user-specified endpoint."""
from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx

from ..core.errors import AuthenticationError, ProviderError
from .base import BaseProvider, ChatMessage, ChatResponse, ProviderConfig


class CustomProvider(BaseProvider):
    """AI provider backed by a custom OpenAI-compatible endpoint."""

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        if not config.base_url:
            raise ProviderError(
                "Custom provider requires a base_url.",
                details="Set the endpoint URL in provider configuration.",
            )
        self._base_url = config.base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=60.0,
                headers=headers,
            )
        return self._client

    async def validate(self) -> bool:
        if not self.config.api_key:
            raise AuthenticationError(
                "No API key configured for custom provider.",
                details="Set an API key in the provider settings.",
            )
        client = self._get_client()
        validate_url = self.config.extra.get("validate_path", "/models") if self.config.extra else "/models"
        try:
            resp = await client.get(validate_url)
            if resp.status_code == 401:
                raise AuthenticationError("Custom provider rejected the API key.")
            if resp.status_code != 200:
                raise ProviderError(
                    f"Custom provider validation failed: HTTP {resp.status_code}",
                    details=resp.text[:500],
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
                        raise AuthenticationError("Custom provider rejected the API key.")
                    if resp.status_code != 200:
                        text = await resp.aread()
                        raise ProviderError(
                            f"Custom provider request failed: HTTP {resp.status_code}",
                            details=text.decode()[:500],
                        )
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if line.startswith("data: "):
                            chunk = line[6:].strip()
                            if chunk == "[DONE]":
                                break
                            try:
                                data = json.loads(chunk)
                                choices = data.get("choices", [])
                                if choices:
                                    content = choices[0].get("delta", {}).get("content")
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
                    raise AuthenticationError("Custom provider rejected the API key.")
                if resp.status_code != 200:
                    raise ProviderError(
                        f"Custom provider request failed: HTTP {resp.status_code}",
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
