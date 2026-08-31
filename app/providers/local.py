"""Local provider — connects to a local LLM inference backend."""
from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx

from ..core.errors import AuthenticationError, ProviderError
from .base import BaseProvider, ChatMessage, ChatResponse, ProviderConfig


class LocalProvider(BaseProvider):
    """AI provider backed by a local inference endpoint.

    Typically used with llama.cpp server, Ollama, or Text Generation Web UI.
    No API key is required, but a base_url must be provided.
    """

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        if not config.base_url:
            raise ProviderError(
                "Local provider requires a base_url.",
                details="Set the local endpoint URL (e.g. http://127.0.0.1:8000/v1).",
            )
        self._base_url = config.base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            # Local providers often don't need auth, but allow optional key
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=60.0,
                headers=headers,
            )
        return self._client

    async def validate(self) -> bool:
        client = self._get_client()
        try:
            resp = await client.get("/models")
            if resp.status_code == 200:
                return True
            raise ProviderError(
                f"Local provider returned HTTP {resp.status_code}.",
                details="Ensure your local inference server is running.",
            )
        except httpx.ConnectError:
            raise ProviderError(
                "Cannot connect to local provider.",
                details=f"Ensure a local LLM server is running at {self._base_url}.",
            )
        except httpx.HTTPError as e:
            raise ProviderError("Local provider validation failed.", details=str(e))
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
                    if resp.status_code != 200:
                        text = await resp.aread()
                        raise ProviderError(
                            f"Local provider request failed: HTTP {resp.status_code}",
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
                if resp.status_code != 200:
                    raise ProviderError(
                        f"Local provider request failed: HTTP {resp.status_code}",
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
        except httpx.ConnectError:
            raise ProviderError(
                "Cannot connect to local provider.",
                details=f"Ensure a local LLM server is running at {self._base_url}.",
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
