"""Tests for Phase 9: Plugin system, Marketplace, and Community features."""
import asyncio
import json
import time
import pytest

from app.core.db import init_db


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Initialize the database for all tests in this module."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())
    yield
    loop.close()


# ── Plugin Loader Tests ──────────────────────────────────────────────


class TestPluginManager:
    """Tests for the plugin loader and lifecycle manager."""

    def test_plugin_manager_init(self):
        from app.plugins.loader import PluginManager
        pm = PluginManager()
        assert pm is not None

    def test_discover_plugins(self):
        from app.plugins.loader import PluginManager
        pm = PluginManager()
        plugins = pm.discover()
        assert isinstance(plugins, list)

    def test_list_available(self):
        from app.plugins.loader import PluginManager
        pm = PluginManager()
        available = pm.list_available()
        assert isinstance(available, list)

    def test_get_installed(self):
        from app.plugins.loader import PluginManager
        pm = PluginManager()
        installed = pm.get_installed()
        assert isinstance(installed, list)

    def test_install_plugin(self):
        from app.plugins.loader import PluginManager
        pm = PluginManager()
        result = pm.install("test-plugin", "1.0.0", {
            "name": "test-plugin",
            "version": "1.0.0",
            "description": "A test plugin",
            "author": "Test",
            "permissions": [],
        })
        assert result["name"] == "test-plugin"
        assert result["version"] == "1.0.0"
        assert result["enabled"] is True
        assert "id" in result
        # Cleanup
        pm.uninstall(result["id"])

    def test_uninstall_plugin(self):
        from app.plugins.loader import PluginManager
        pm = PluginManager()
        result = pm.install("test-uninstall", "1.0.0", {
            "name": "test-uninstall",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
        })
        plugin_id = result["id"]
        ok = pm.uninstall(plugin_id)
        assert ok is True
        # Verify removed
        installed = pm.get_installed()
        assert all(p["id"] != plugin_id for p in installed)

    def test_toggle_plugin(self):
        from app.plugins.loader import PluginManager
        pm = PluginManager()
        result = pm.install("test-toggle", "1.0.0", {
            "name": "test-toggle",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
        })
        plugin_id = result["id"]
        pm.toggle(plugin_id, False)
        installed = pm.get_installed()
        plugin = [p for p in installed if p["id"] == plugin_id]
        assert len(plugin) == 1
        assert plugin[0]["enabled"] is False
        # Cleanup
        pm.uninstall(plugin_id)

    def test_validate_manifest_valid(self):
        from app.plugins.loader import PluginManager
        pm = PluginManager()
        ok, err = pm.validate_manifest({
            "name": "test",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
        })
        assert ok is True
        assert err == ""

    def test_validate_manifest_missing_keys(self):
        from app.plugins.loader import PluginManager
        pm = PluginManager()
        ok, err = pm.validate_manifest({"name": "test"})
        assert ok is False
        assert "Missing" in err

    def test_validate_manifest_bad_version(self):
        from app.plugins.loader import PluginManager
        pm = PluginManager()
        ok, err = pm.validate_manifest({
            "name": "test",
            "version": 123,
            "description": "Test",
            "author": "Test",
        })
        assert ok is False
        assert "Version" in err

    def test_get_plugin_info(self):
        from app.plugins.loader import PluginManager
        pm = PluginManager()
        # Should return None for nonexistent
        info = pm.get_plugin_info("nonexistent-plugin-xyz")
        assert info is None


# ── Marketplace Tests ────────────────────────────────────────────────


class TestMarketplace:
    """Tests for the extension marketplace client."""

    def test_marketplace_init(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        assert mc is not None

    def test_search_all(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        results = mc.search()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_search_by_query(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        results = mc.search("nmap")
        assert len(results) >= 1
        assert results[0]["name"] == "nmap-scanner"

    def test_search_by_category(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        results = mc.search(category="security")
        assert len(results) >= 1
        assert all(p["category"] == "security" for p in results)

    def test_search_by_tags(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        results = mc.search(tags=["python"])
        assert len(results) >= 1

    def test_get_featured(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        featured = mc.get_featured()
        assert len(featured) > 0
        assert all(p.get("featured") for p in featured)

    def test_get_trending(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        trending = mc.get_trending()
        assert len(trending) > 0
        # Should be sorted by downloads descending
        for i in range(len(trending) - 1):
            assert trending[i].get("downloads", 0) >= trending[i+1].get("downloads", 0)

    def test_get_categories(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        categories = mc.get_categories()
        assert isinstance(categories, list)
        assert len(categories) > 0
        for cat in categories:
            assert "name" in cat
            assert "count" in cat

    def test_get_plugin(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        plugin = mc.get_plugin("nmap-scanner")
        assert plugin is not None
        assert plugin["name"] == "nmap-scanner"

    def test_get_plugin_not_found(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        plugin = mc.get_plugin("nonexistent")
        assert plugin is None

    def test_get_reviews(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        reviews = mc.get_reviews("nmap-scanner")
        assert isinstance(reviews, list)
        assert len(reviews) > 0

    def test_get_stats(self):
        from app.plugins.marketplace import MarketplaceClient
        mc = MarketplaceClient()
        stats = mc.get_stats()
        assert "total_plugins" in stats
        assert "total_downloads" in stats
        assert stats["total_plugins"] > 0


# ── Community Tests ──────────────────────────────────────────────────


class TestCommunity:
    """Tests for the community manager: favorites, ratings, collections."""

    def test_community_init(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        assert cm is not None

    def test_add_favorite(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        result = cm.add_favorite("test-fav-plugin")
        assert "id" in result
        assert result["plugin"] == "test-fav-plugin"
        # Cleanup
        cm.remove_favorite("test-fav-plugin")

    def test_get_favorites(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        cm.add_favorite("fav-test-2")
        favs = cm.get_favorites()
        assert isinstance(favs, list)
        # Cleanup
        cm.remove_favorite("fav-test-2")

    def test_is_favorite(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        cm.add_favorite("fav-check")
        assert cm.is_favorite("fav-check") is True
        cm.remove_favorite("fav-check")
        assert cm.is_favorite("fav-check") is False

    def test_rate_plugin(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        result = cm.rate_plugin("test-rate-plugin", 4, "Good plugin")
        assert result["rating"] == 4
        assert result["comment"] == "Good plugin"

    def test_rate_plugin_invalid(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        with pytest.raises(ValueError):
            cm.rate_plugin("test", 0)

    def test_get_ratings(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        cm.rate_plugin("test-ratings", 5, "Excellent")
        ratings = cm.get_ratings("test-ratings")
        assert len(ratings) >= 1

    def test_get_average_rating(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        cm.rate_plugin("avg-test", 3, "")
        cm.rate_plugin("avg-test", 5, "")
        avg = cm.get_average_rating("avg-test")
        assert avg >= 3.0
        assert avg <= 5.0

    def test_create_collection(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        result = cm.create_collection("Security Tools", "A collection", ["nmap-scanner", "password-audit"])
        assert result["name"] == "Security Tools"
        assert len(result["plugins"]) == 2
        # Cleanup
        cm.delete_collection(result["id"])

    def test_get_collections(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        cols = cm.get_collections()
        assert isinstance(cols, list)

    def test_update_collection(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        result = cm.create_collection("Update Test", "Original")
        ok = cm.update_collection(result["id"], name="Updated Test")
        assert ok is True
        updated = cm.get_collection(result["id"])
        assert updated["name"] == "Updated Test"
        # Cleanup
        cm.delete_collection(result["id"])

    def test_delete_collection(self):
        from app.plugins.community import CommunityManager
        cm = CommunityManager()
        result = cm.create_collection("Delete Test")
        ok = cm.delete_collection(result["id"])
        assert ok is True
        assert cm.get_collection(result["id"]) is None
