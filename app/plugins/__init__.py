"""Plugin system for NEXORA — discover, load, manage extensions."""

from .loader import PluginManager
from .marketplace import MarketplaceClient
from .community import CommunityManager

__all__ = ["PluginManager", "MarketplaceClient", "CommunityManager"]
