"""Provider manager — registers, tracks, and instantiates providers."""
from __future__ import annotations

from typing import Type

from loguru import logger

from ..core import secrets
from ..core.db import execute
from ..core.errors import ConfigurationError, ProviderError
from .base import BaseProvider, ChatMessage, ChatResponse, ProviderConfig
from .custom import CustomProvider
from .local import LocalProvider
from .openrouter import OpenRouterProvider

_PROVIDER_TYPES: dict[str, Type[BaseProvider]] = {
    "openrouter": OpenRouterProvider,
    "custom": CustomProvider,
    "local": LocalProvider,
}


def register_provider_type(type_name: str, cls: Type[BaseProvider]) -> None:
    """Register a custom provider type at runtime."""
    _PROVIDER_TYPES[type_name] = cls


class ProviderManager:
    """Manages provider registration, configuration, and instantiation."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    async def load_from_db(self) -> None:
        """Load provider configurations from the database and instantiate."""
        rows = await execute(
            "SELECT * FROM providers",
            fetch="all",
        ) or []

        for row in rows:
            await self._load_provider_from_row(row)

    async def _load_provider_from_row(self, row: dict) -> None:
        """Instantiate a provider from a database row."""
        provider_type = row["type"]
        if provider_type not in _PROVIDER_TYPES:
            logger.warning(f"Unknown provider type '{provider_type}' for provider '{row['id']}'")
            return

        # Retrieve API key from secure storage
        api_key = None
        if row["configured"]:
            try:
                api_key = secrets.retrieve_api_key(row["id"])
            except Exception as e:
                logger.warning(f"Could not retrieve API key for provider '{row['id']}': {e}")

        import json

        extra = json.loads(row["extra"]) if row.get("extra") else None

        config = ProviderConfig(
            id=row["id"],
            type=provider_type,
            name=row["name"],
            model=row["model"],
            api_key=api_key,
            base_url=row.get("base_url"),
            extra=extra,
            configured=bool(row.get("configured", 0)),
        )

        cls = _PROVIDER_TYPES[provider_type]
        try:
            provider = cls(config)
            self._providers[config.id] = provider
            logger.info(f"Loaded provider: {config.id} ({config.type})")
        except Exception as e:
            logger.error(f"Failed to instantiate provider '{config.id}': {e}")

    def list_providers(self) -> list[ProviderConfig]:
        """Return metadata about all registered providers."""
        return [p.config for p in self._providers.values()]

    def get_provider(self, provider_id: str) -> BaseProvider:
        """Get an instantiated provider by ID."""
        if provider_id not in self._providers:
            raise ProviderError(
                f"Provider '{provider_id}' not found.",
                details="Use list_providers() to see available providers.",
            )
        return self._providers[provider_id]

    def get_default_provider(self) -> BaseProvider | None:
        """Return the first configured provider, or None."""
        for p in self._providers.values():
            if p.configured:
                return p
        return None

    async def add_provider(
        self,
        provider_type: str,
        name: str,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        extra: dict | None = None,
    ) -> ProviderConfig:
        """Add a new provider configuration."""
        if provider_type not in _PROVIDER_TYPES:
            raise ConfigurationError(
                f"Unknown provider type: '{provider_type}'.",
                details=f"Available types: {', '.join(_PROVIDER_TYPES.keys())}",
            )

        import json
        import time

        provider_id = f"{provider_type}-{name.lower().replace(' ', '-')}"
        now = time.time()

        configured = False
        if api_key:
            secrets.store_api_key(provider_id, api_key)
            configured = True

        # If no API key was stored, try retrieving one (e.g., re-adding)
        if not configured:
            existing = secrets.retrieve_api_key(provider_id)
            if existing:
                api_key = existing
                configured = True

        await execute(
            """
            INSERT OR REPLACE INTO providers (id, type, name, model, base_url, extra, configured, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provider_id,
                provider_type,
                name,
                model,
                base_url,
                json.dumps(extra) if extra else None,
                1 if configured else 0,
                now,
                now,
            ),
        )

        config = ProviderConfig(
            id=provider_id,
            type=provider_type,
            name=name,
            model=model,
            api_key=api_key,
            base_url=base_url,
            extra=extra,
            configured=configured,
        )

        cls = _PROVIDER_TYPES[provider_type]
        provider = cls(config)
        self._providers[provider_id] = provider
        logger.info(f"Added provider: {provider_id}")

        return config

    async def remove_provider(self, provider_id: str) -> None:
        """Remove a provider and delete its stored credentials."""
        if provider_id in self._providers:
            await self._providers[provider_id].close()
            del self._providers[provider_id]

        secrets.delete_api_key(provider_id)

        await execute("DELETE FROM providers WHERE id = ?", (provider_id,))
        logger.info(f"Removed provider: {provider_id}")

    async def test_connection(self, provider_id: str) -> bool:
        """Test the connection for a provider."""
        if provider_id not in self._providers:
            raise ProviderError(f"Provider '{provider_id}' not found.")
        return await self._providers[provider_id].validate()

    async def shutdown(self) -> None:
        """Close all providers."""
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception as e:
                logger.warning(f"Error closing provider '{provider.id}': {e}")
        self._providers.clear()


manager = ProviderManager()
