"""Local AI fallback — detect and use local AI models (Ollama, llama.cpp)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from loguru import logger


async def detect_ollama(base_url: str = "http://localhost:11434") -> dict[str, Any] | None:
    """Detect if Ollama is running and list available models."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            if models:
                return {"backend": "ollama", "url": base_url, "models": models}
    except Exception:
        pass
    return None


async def detect_llama_cpp(port: int = 8080) -> dict[str, Any] | None:
    """Detect if llama.cpp server is running."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"http://localhost:{port}/health")
            if resp.status_code == 200:
                return {"backend": "llama_cpp", "url": f"http://localhost:{port}", "models": ["local"]}
    except Exception:
        pass
    return None


async def detect_local_ai() -> dict[str, Any] | None:
    """Detect any available local AI backend."""
    ollama = await detect_ollama()
    if ollama:
        return ollama

    llama = await detect_llama_cpp()
    if llama:
        return llama

    return None


async def ollama_chat(
    message: str,
    model: str = "",
    base_url: str = "http://localhost:11434",
) -> str:
    """Send a chat message to Ollama."""
    if not model:
        # Get first available model
        info = await detect_ollama(base_url)
        if info and info["models"]:
            model = info["models"][0]
        else:
            raise ValueError("No Ollama models available")

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": message, "stream": False},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")


async def llama_cpp_chat(
    message: str,
    port: int = 8080,
) -> str:
    """Send a chat message to llama.cpp server."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"http://localhost:{port}/completion",
            json={"prompt": message, "n_predict": 512},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", "")


async def local_chat(message: str, model: str = "") -> str:
    """Route a chat message to the best available local AI backend."""
    info = await detect_local_ai()
    if not info:
        raise ConnectionError("No local AI backend detected. Install Ollama or llama.cpp.")

    if info["backend"] == "ollama":
        return await ollama_chat(message, model=model or (info["models"][0] if info["models"] else ""), base_url=info["url"])
    elif info["backend"] == "llama_cpp":
        return await llama_cpp_chat(message)

    raise ConnectionError(f"Unknown backend: {info['backend']}")
