"""Web search tool — search the web using DuckDuckGo (no API key required)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


async def _duckduckgo_search(query: str, max_results: int = 10) -> list[dict[str, str]]:
    """Search DuckDuckGo HTML lite and parse results."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for result_div in soup.select(".result"):
        title_el = result_div.select_one(".result__a")
        snippet_el = result_div.select_one(".result__snippet")
        url_el = result_div.select_one(".result__url")

        if not title_el:
            continue

        href = title_el.get("href", "")
        # DuckDuckGo wraps URLs in a redirect; extract the actual URL
        if "uddg=" in href:
            match = re.search(r"uddg=([^&]+)", href)
            if match:
                from urllib.parse import unquote
                href = unquote(match.group(1))

        results.append({
            "title": title_el.get_text(strip=True),
            "url": href,
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            "display_url": url_el.get_text(strip=True) if url_el else href,
        })

        if len(results) >= max_results:
            break

    return results


async def _brave_search(query: str, max_results: int = 10) -> list[dict[str, str]]:
    """Fallback: search using Brave Search HTML."""
    url = f"https://search.brave.com/search?q={quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for item in soup.select(".snippet"):
        title_el = item.select_one(".snippet-title")
        desc_el = item.select_one(".snippet-description")
        url_el = item.select_one(".snippet-url")

        if not title_el:
            continue

        results.append({
            "title": title_el.get_text(strip=True),
            "url": url_el.get_text(strip=True) if url_el else "",
            "snippet": desc_el.get_text(strip=True) if desc_el else "",
            "display_url": url_el.get_text(strip=True) if url_el else "",
        })

        if len(results) >= max_results:
            break

    return results


class WebSearchTool(BaseTool):
    """Search the web using DuckDuckGo."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="internet.search",
            description="Search the web for information using DuckDuckGo.",
            category="internet",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=20.0,
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results (default 10)"},
                },
                "required": ["query"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("query"):
            return "query is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        query = inputs["query"]
        max_results = inputs.get("max_results", 10)

        try:
            results = await _duckduckgo_search(query, max_results)
            if not results:
                # Fallback to Brave
                results = await _brave_search(query, max_results)

            self.log_action("search", query, details=f"results={len(results)}")
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results,
                    "total": len(results),
                },
            )
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
            return ToolResult(success=False, error=f"Search failed: {e}")
