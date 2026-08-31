"""Page fetch tool — fetch URLs and extract readable content."""

from __future__ import annotations

from typing import Any

import httpx
import html2text
from bs4 import BeautifulSoup
from loguru import logger

from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


def _extract_readability(soup: BeautifulSoup) -> str:
    """Extract main content using simple heuristics (no readability library needed)."""
    # Remove non-content elements
    for tag in soup.select("script, style, nav, header, footer, aside, .sidebar, .nav, .menu, .ad, .advertisement, .cookie, .popup"):
        tag.decompose()

    # Try article or main content
    content_el = soup.select_one("article, main, [role='main'], .content, .post, .entry-content, .article-body")
    if not content_el:
        content_el = soup.body or soup

    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0  # Don't wrap
    h.ignore_emphasis = False
    h.ignore_tables = False

    text = h.handle(str(content_el))
    # Clean up excessive blank lines
    lines = [line.rstrip() for line in text.split("\n")]
    cleaned = "\n".join(line for i, line in enumerate(lines) if line or (i > 0 and lines[i - 1]))
    return cleaned.strip()


class FetchPageTool(BaseTool):
    """Fetch a URL and extract readable content."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="internet.fetch",
            description="Fetch a web page and extract its readable content.",
            category="internet",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=30.0,
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "max_chars": {"type": "integer", "description": "Max characters to return (default 20000)"},
                    "format": {
                        "type": "string",
                        "enum": ["text", "markdown", "html"],
                        "description": "Output format",
                    },
                },
                "required": ["url"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        url = inputs.get("url", "")
        if not url:
            return "url is required"
        if not url.startswith(("http://", "https://")):
            return "url must start with http:// or https://"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        url = inputs["url"]
        max_chars = inputs.get("max_chars", 20000)
        fmt = inputs.get("format", "markdown")

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        try:
            async with httpx.AsyncClient(
                timeout=20, follow_redirects=True, max_redirects=5
            ) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")

            # If it's JSON, return raw
            if "json" in content_type:
                text = resp.text[:max_chars]
                self.log_action("fetch", url, details=f"json len={len(text)}")
                return ToolResult(
                    success=True,
                    data={
                        "url": str(resp.url),
                        "title": "",
                        "content": text,
                        "content_type": content_type,
                        "status_code": resp.status_code,
                        "truncated": len(resp.text) > max_chars,
                    },
                )

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract title
            title_tag = soup.select_one("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # Extract meta description
            meta_desc = ""
            meta_tag = soup.select_one('meta[name="description"]')
            if meta_tag:
                meta_desc = meta_tag.get("content", "")

            if fmt == "html":
                content = resp.text[:max_chars]
            elif fmt == "text":
                h = html2text.HTML2Text()
                h.ignore_links = True
                h.ignore_images = True
                h.body_width = 0
                content = h.handle(resp.text)[:max_chars]
            else:  # markdown
                content = _extract_readability(soup)[:max_chars]

            self.log_action("fetch", url, details=f"fmt={fmt} len={len(content)}")
            return ToolResult(
                success=True,
                data={
                    "url": str(resp.url),
                    "title": title,
                    "description": meta_desc,
                    "content": content,
                    "content_type": content_type,
                    "status_code": resp.status_code,
                    "truncated": len(content) >= max_chars,
                },
            )
        except httpx.TimeoutException:
            return ToolResult(success=False, error=f"Timeout fetching {url}")
        except httpx.HTTPStatusError as e:
            return ToolResult(success=False, error=f"HTTP {e.response.status_code}: {url}")
        except Exception as e:
            return ToolResult(success=False, error=f"Fetch failed: {e}")


class FetchJsonTool(BaseTool):
    """Fetch a JSON API endpoint."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="internet.fetch_json",
            description="Fetch a JSON API endpoint and return parsed data.",
            category="internet",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=20.0,
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "API endpoint URL"},
                    "method": {"type": "string", "enum": ["GET", "POST"], "description": "HTTP method"},
                    "headers": {"type": "object", "description": "Additional headers"},
                    "body": {"type": "object", "description": "Request body (for POST)"},
                },
                "required": ["url"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        url = inputs.get("url", "")
        if not url:
            return "url is required"
        if not url.startswith(("http://", "https://")):
            return "url must start with http:// or https://"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        url = inputs["url"]
        method = inputs.get("method", "GET").upper()
        extra_headers = inputs.get("headers", {})
        body = inputs.get("body")

        headers = {
            "User-Agent": "NEXORA/1.0",
            "Accept": "application/json",
            **extra_headers,
        }

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                if method == "POST":
                    resp = await client.post(url, headers=headers, json=body)
                else:
                    resp = await client.get(url, headers=headers)
                resp.raise_for_status()

            data = resp.json()
            self.log_action("fetch_json", url, details=f"method={method}")
            return ToolResult(
                success=True,
                data={
                    "url": str(resp.url),
                    "status_code": resp.status_code,
                    "data": data,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"API request failed: {e}")


def register_fetch_tools(registry: Any) -> None:
    """Register fetch tools."""
    registry.register(FetchPageTool())
    registry.register(FetchJsonTool())
