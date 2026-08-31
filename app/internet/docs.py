"""Documentation lookup tool — search developer documentation sources."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


async def _search_mdn(query: str) -> list[dict[str, str]]:
    """Search MDN Web Docs."""
    url = f"https://developer.mozilla.org/api/v1/search?q={quote_plus(query)}&size=5"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for doc in data.get("documents", []):
        results.append({
            "title": doc.get("title", ""),
            "url": f"https://developer.mozilla.org{doc.get('mdn_url', '')}",
            "summary": doc.get("summary", ""),
            "source": "MDN",
        })
    return results


async def _search_stackoverflow(query: str) -> list[dict[str, str]]:
    """Search Stack Overflow via API."""
    url = f"https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=relevance&q={quote_plus(query)}&site=stackoverflow&pagesize=5&filter=withbody"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("items", []):
        # Strip HTML from title
        title = BeautifulSoup(item.get("title", ""), "html.parser").get_text()
        results.append({
            "title": title,
            "url": item.get("link", ""),
            "summary": f"Score: {item.get('score', 0)} | Answers: {item.get('answer_count', 0)}",
            "source": "Stack Overflow",
        })
    return results


async def _search_github_docs(query: str) -> list[dict[str, str]]:
    """Search GitHub for documentation repos."""
    url = f"https://api.github.com/search/repositories?q={quote_plus(query + ' docs')}&sort=stars&per_page=3"
    headers = {"Accept": "application/vnd.github.v3+json"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for repo in data.get("items", []):
        results.append({
            "title": repo.get("full_name", ""),
            "url": repo.get("html_url", ""),
            "summary": repo.get("description", "")[:200],
            "source": "GitHub",
        })
    return results


class DocsLookupTool(BaseTool):
    """Search developer documentation (MDN, Stack Overflow, GitHub)."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="internet.docs",
            description="Look up developer documentation from MDN, Stack Overflow, and GitHub.",
            category="internet",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=20.0,
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Documentation search query"},
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Sources to search (mdn, stackoverflow, github)",
                    },
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
        sources = inputs.get("sources", ["mdn", "stackoverflow", "github"])

        all_results: list[dict[str, str]] = []
        errors: list[str] = []

        if "mdn" in sources:
            try:
                mdn = await _search_mdn(query)
                all_results.extend(mdn)
            except Exception as e:
                errors.append(f"MDN: {e}")

        if "stackoverflow" in sources:
            try:
                so = await _search_stackoverflow(query)
                all_results.extend(so)
            except Exception as e:
                errors.append(f"SO: {e}")

        if "github" in sources:
            try:
                gh = await _search_github_docs(query)
                all_results.extend(gh)
            except Exception as e:
                errors.append(f"GitHub: {e}")

        self.log_action("docs_lookup", query, details=f"results={len(all_results)} errors={len(errors)}")
        return ToolResult(
            success=True,
            data={
                "query": query,
                "results": all_results,
                "total": len(all_results),
                "errors": errors,
            },
        )


def register_docs_tools(registry: Any) -> None:
    """Register documentation tools."""
    registry.register(DocsLookupTool())
