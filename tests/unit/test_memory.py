"""Tests for memory system — store, retrieve, search, delete."""

import asyncio

import pytest

from app.core.db import init_db


class TestMemoryStore:
    def test_set_and_get(self):
        asyncio.run(init_db())
        from app.core.memory import MemoryStore
        store = MemoryStore()
        asyncio.run(store.set("global", "test_key", "test_value"))
        entry = asyncio.run(store.get("global", "test_key"))
        assert entry is not None
        assert entry["value"] == "test_value"
        assert entry["scope"] == "global"

    def test_get_nonexistent(self):
        asyncio.run(init_db())
        from app.core.memory import MemoryStore
        store = MemoryStore()
        entry = asyncio.run(store.get("global", "nonexistent_key"))
        assert entry is None

    def test_delete(self):
        asyncio.run(init_db())
        from app.core.memory import MemoryStore
        store = MemoryStore()
        asyncio.run(store.set("global", "to_delete", "value"))
        asyncio.run(store.delete("global", "to_delete"))
        entry = asyncio.run(store.get("global", "to_delete"))
        assert entry is None

    def test_search(self):
        asyncio.run(init_db())
        from app.core.memory import MemoryStore
        store = MemoryStore()
        asyncio.run(store.set("global", "python_pref", "likes dark theme"))
        asyncio.run(store.set("global", "user_name", "Alice"))
        results = asyncio.run(store.search(query="python"))
        assert len(results) >= 1
        assert any("python" in r["key"] for r in results)

    def test_search_by_scope(self):
        asyncio.run(init_db())
        from app.core.memory import MemoryStore
        store = MemoryStore()
        asyncio.run(store.set("global", "g1", "global val"))
        asyncio.run(store.set("project", "p1", "project val"))
        results = asyncio.run(store.search(scope="project"))
        assert all(r["scope"] == "project" for r in results)

    def test_clear_scope(self):
        asyncio.run(init_db())
        from app.core.memory import MemoryStore
        store = MemoryStore()
        asyncio.run(store.set("project", "k1", "v1"))
        asyncio.run(store.set("project", "k2", "v2"))
        asyncio.run(store.set("global", "k3", "v3"))
        count = asyncio.run(store.clear("project"))
        assert count == 2
        remaining = asyncio.run(store.search(scope="project"))
        assert len(remaining) == 0
        global_remaining = asyncio.run(store.search(scope="global"))
        assert len(global_remaining) >= 1

    def test_list_scopes(self):
        asyncio.run(init_db())
        from app.core.memory import MemoryStore
        store = MemoryStore()
        asyncio.run(store.set("global", "sk1", "v"))
        asyncio.run(store.set("project", "sk2", "v"))
        scopes = asyncio.run(store.list_scopes())
        assert len(scopes) >= 2
        scope_names = {s["scope"] for s in scopes}
        assert "global" in scope_names
        assert "project" in scope_names


class TestMemoryTools:
    def test_set_tool_spec(self):
        from app.core.memory import MemorySetTool
        tool = MemorySetTool()
        assert tool.spec().name == "memory.set"
        assert tool.spec().category == "memory"

    def test_get_tool_spec(self):
        from app.core.memory import MemoryGetTool
        tool = MemoryGetTool()
        assert tool.spec().name == "memory.get"

    def test_search_tool_spec(self):
        from app.core.memory import MemorySearchTool
        tool = MemorySearchTool()
        assert tool.spec().name == "memory.search"

    def test_delete_tool_spec(self):
        from app.core.memory import MemoryDeleteTool
        tool = MemoryDeleteTool()
        assert tool.spec().name == "memory.delete"

    def test_clear_tool_spec(self):
        from app.core.memory import MemoryClearTool
        tool = MemoryClearTool()
        assert tool.spec().name == "memory.clear"

    def test_scopes_tool_spec(self):
        from app.core.memory import MemoryScopesTool
        tool = MemoryScopesTool()
        assert tool.spec().name == "memory.scopes"

    def test_set_validate(self):
        from app.core.memory import MemorySetTool
        tool = MemorySetTool()
        error = asyncio.run(tool.validate_inputs({"scope": "", "key": "", "value": ""}))
        assert error is not None

    def test_set_execute(self):
        asyncio.run(init_db())
        from app.core.memory import MemorySetTool
        tool = MemorySetTool()
        result = asyncio.run(tool.execute({
            "scope": "global",
            "key": "tool_test",
            "value": "tool value",
        }))
        assert result.success
        assert result.data["key"] == "tool_test"


class TestRegistry:
    def test_register_memory(self):
        from app.tools.registry import ToolRegistry
        reg = ToolRegistry()
        from app.core.memory import register_memory_tools
        register_memory_tools(reg)
        tools = reg.list_tools(category="memory")
        names = {t.name for t in tools}
        assert "memory.set" in names
        assert "memory.get" in names
        assert "memory.search" in names
        assert "memory.delete" in names
        assert "memory.clear" in names
        assert "memory.scopes" in names
        assert len(tools) == 6
