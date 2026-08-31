"""Tests for internet module — search, fetch, docs, browser."""

import asyncio

import pytest


# ============================================================
# Web Search
# ============================================================

class TestWebSearchTool:
    def test_spec(self):
        from app.internet.search import WebSearchTool
        tool = WebSearchTool()
        spec = tool.spec()
        assert spec.name == "internet.search"
        assert spec.category == "internet"

    def test_validate_empty_query(self):
        from app.internet.search import WebSearchTool
        tool = WebSearchTool()
        error = asyncio.run(tool.validate_inputs({"query": ""}))
        assert error is not None

    def test_validate_valid_query(self):
        from app.internet.search import WebSearchTool
        tool = WebSearchTool()
        error = asyncio.run(tool.validate_inputs({"query": "python asyncio"}))
        assert error is None


# ============================================================
# Page Fetch
# ============================================================

class TestFetchPageTool:
    def test_spec(self):
        from app.internet.fetch import FetchPageTool
        tool = FetchPageTool()
        spec = tool.spec()
        assert spec.name == "internet.fetch"
        assert spec.category == "internet"

    def test_validate_empty_url(self):
        from app.internet.fetch import FetchPageTool
        tool = FetchPageTool()
        error = asyncio.run(tool.validate_inputs({"url": ""}))
        assert error is not None

    def test_validate_invalid_url(self):
        from app.internet.fetch import FetchPageTool
        tool = FetchPageTool()
        error = asyncio.run(tool.validate_inputs({"url": "ftp://example.com"}))
        assert error is not None

    def test_validate_valid_url(self):
        from app.internet.fetch import FetchPageTool
        tool = FetchPageTool()
        error = asyncio.run(tool.validate_inputs({"url": "https://example.com"}))
        assert error is None


class TestFetchJsonTool:
    def test_spec(self):
        from app.internet.fetch import FetchJsonTool
        tool = FetchJsonTool()
        spec = tool.spec()
        assert spec.name == "internet.fetch_json"

    def test_validate_empty_url(self):
        from app.internet.fetch import FetchJsonTool
        tool = FetchJsonTool()
        error = asyncio.run(tool.validate_inputs({"url": ""}))
        assert error is not None

    def test_validate_valid_url(self):
        from app.internet.fetch import FetchJsonTool
        tool = FetchJsonTool()
        error = asyncio.run(tool.validate_inputs({"url": "https://api.example.com/data"}))
        assert error is None


# ============================================================
# Documentation Lookup
# ============================================================

class TestDocsLookupTool:
    def test_spec(self):
        from app.internet.docs import DocsLookupTool
        tool = DocsLookupTool()
        spec = tool.spec()
        assert spec.name == "internet.docs"
        assert spec.category == "internet"

    def test_validate_empty_query(self):
        from app.internet.docs import DocsLookupTool
        tool = DocsLookupTool()
        error = asyncio.run(tool.validate_inputs({"query": ""}))
        assert error is not None

    def test_validate_valid_query(self):
        from app.internet.docs import DocsLookupTool
        tool = DocsLookupTool()
        error = asyncio.run(tool.validate_inputs({"query": "asyncio event loop"}))
        assert error is None


# ============================================================
# Browser Integration
# ============================================================

class TestOpenBrowserTool:
    def test_spec(self):
        from app.internet.browser import OpenBrowserTool
        tool = OpenBrowserTool()
        spec = tool.spec()
        assert spec.name == "internet.open"
        assert spec.category == "internet"
        assert spec.risk_level.value == "low"

    def test_validate_empty_url(self):
        from app.internet.browser import OpenBrowserTool
        tool = OpenBrowserTool()
        error = asyncio.run(tool.validate_inputs({"url": ""}))
        assert error is not None

    def test_validate_invalid_url(self):
        from app.internet.browser import OpenBrowserTool
        tool = OpenBrowserTool()
        error = asyncio.run(tool.validate_inputs({"url": "javascript:alert(1)"}))
        assert error is not None

    def test_validate_valid_urls(self):
        from app.internet.browser import OpenBrowserTool
        tool = OpenBrowserTool()
        for url in ["https://example.com", "http://localhost:3000", "file:///tmp/test.html"]:
            error = asyncio.run(tool.validate_inputs({"url": url}))
            assert error is None, f"Expected valid for {url}"


# ============================================================
# Registry Integration
# ============================================================

class TestInternetRegistry:
    def test_register_all(self):
        from app.tools.registry import ToolRegistry
        reg = ToolRegistry()
        from app.internet.search import WebSearchTool
        from app.internet.fetch import register_fetch_tools
        from app.internet.docs import register_docs_tools
        from app.internet.browser import register_browser_tools

        reg.register(WebSearchTool())
        register_fetch_tools(reg)
        register_docs_tools(reg)
        register_browser_tools(reg)

        tools = reg.list_tools()
        names = {t.name for t in tools}
        assert "internet.search" in names
        assert "internet.fetch" in names
        assert "internet.fetch_json" in names
        assert "internet.docs" in names
        assert "internet.open" in names
        assert len(tools) == 5

    def test_internet_category(self):
        from app.tools.registry import ToolRegistry
        reg = ToolRegistry()
        from app.internet.search import WebSearchTool
        from app.internet.fetch import register_fetch_tools
        from app.internet.docs import register_docs_tools
        from app.internet.browser import register_browser_tools

        reg.register(WebSearchTool())
        register_fetch_tools(reg)
        register_docs_tools(reg)
        register_browser_tools(reg)

        internet_tools = reg.list_tools(category="internet")
        assert len(internet_tools) == 5


# ============================================================
# Live Integration Tests (require network)
# ============================================================

class TestLiveSearch:
    @pytest.mark.skipif(
        not pytest.importorskip("httpx"),
        reason="httpx not available"
    )
    def test_search_returns_results(self):
        from app.internet.search import WebSearchTool
        tool = WebSearchTool()
        result = asyncio.run(tool.execute({"query": "python programming", "max_results": 3}))
        assert result.success
        assert len(result.data["results"]) > 0
        first = result.data["results"][0]
        assert "title" in first
        assert "url" in first

    def test_fetch_example_com(self):
        from app.internet.fetch import FetchPageTool
        tool = FetchPageTool()
        result = asyncio.run(tool.execute({"url": "https://example.com", "max_chars": 1000}))
        assert result.success
        assert "Example Domain" in result.data.get("title", "") or "example" in result.data.get("content", "").lower()

    def test_fetch_json_placeholder(self):
        from app.internet.fetch import FetchJsonTool
        tool = FetchJsonTool()
        result = asyncio.run(tool.execute({"url": "https://jsonplaceholder.typicode.com/todos/1"}))
        assert result.success
        data = result.data["data"]
        assert "userId" in data or "id" in data
