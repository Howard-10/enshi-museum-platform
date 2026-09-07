"""Guarded Tavily-compatible web search for future official-source retrieval.

No network request can occur unless both a provider key and WEB_SEARCH_ENABLED
are explicitly configured. Search results are transient evidence only; callers
must never write them into the museum knowledge base.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.db.models.core import WebSearchAudit


class WebSearchDisabledError(RuntimeError):
    """Raised before a provider client is constructed while web search is disabled."""


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    excerpt: str
    domain: str


@dataclass(frozen=True)
class WebSearchResponse:
    results: list[WebSearchResult]
    request_id: str | None
    latency_ms: int


class WebSearchProvider(Protocol):
    async def search(self, query: str, *, allowed_domains: list[str]) -> WebSearchResponse: ...


def allowed_domains(config: Settings = settings) -> list[str]:
    return [
        domain.strip().lower()
        for domain in config.web_search_allowed_domains.split(",")
        if domain.strip()
    ]


async def monthly_request_count(session: AsyncSession) -> int:
    """Count this month's basic-search requests for the configured budget."""

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.count(WebSearchAudit.id)).where(WebSearchAudit.created_at >= month_start)
    )
    return int(result.scalar_one())


def require_web_search(config: Settings = settings) -> None:
    if not config.web_search_enabled:
        raise WebSearchDisabledError(
            "Web search is disabled. Set WEB_SEARCH_ENABLED=true after approval."
        )
    if config.web_search_provider != "tavily":
        raise ValueError(f"Unsupported web search provider: {config.web_search_provider}")
    if not config.tavily_api_key:
        raise ValueError("Tavily configuration is incomplete: TAVILY_API_KEY")
    if config.web_search_monthly_request_limit <= 0:
        raise ValueError("Web search is blocked until WEB_SEARCH_MONTHLY_REQUEST_LIMIT is positive")


class TavilyWebSearchProvider:
    """Minimal Tavily REST adapter using only source snippets, never Tavily's AI answer."""

    endpoint = "https://api.tavily.com/search"

    def __init__(self, *, api_key: str, max_results: int = 5) -> None:
        self.api_key = api_key
        self.max_results = max_results

    async def search(self, query: str, *, allowed_domains: list[str]) -> WebSearchResponse:
        started = time.perf_counter()
        payload = {
            "query": query,
            "search_depth": "basic",
            "max_results": self.max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_domains": allowed_domains,
            "country": "china",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
        payload_response = response.json()
        allowlist = set(allowed_domains)
        results: list[WebSearchResult] = []
        for item in payload_response.get("results", []):
            url = str(item.get("url", ""))
            domain = (urlparse(url).hostname or "").lower()
            if not any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowlist):
                continue
            results.append(
                WebSearchResult(
                    title=str(item.get("title", ""))[:500],
                    url=url,
                    excerpt=str(item.get("content", ""))[:2_000],
                    domain=domain,
                )
            )
        return WebSearchResponse(
            results=results,
            request_id=payload_response.get("request_id"),
            latency_ms=round((time.perf_counter() - started) * 1_000),
        )


def create_web_search_provider(config: Settings = settings) -> WebSearchProvider:
    """Construct a provider only after explicit enablement and budget approval."""

    require_web_search(config)
    return TavilyWebSearchProvider(api_key=config.tavily_api_key or "")


async def record_search_audit(
    session: AsyncSession,
    *,
    session_id: str | None,
    query: str,
    attempt: int,
    provider: str,
    status: str,
    request_id: str | None = None,
    latency_ms: int | None = None,
    result_domains: list[str] | None = None,
    error_type: str | None = None,
) -> None:
    """Persist metadata only; query text and credentials are intentionally excluded."""

    session.add(
        WebSearchAudit(
            session_id=session_id,
            query_sha256=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            attempt=attempt,
            provider=provider,
            status=status,
            request_id=request_id,
            latency_ms=latency_ms,
            result_domains=sorted(set(result_domains or [])),
            error_type=error_type,
        )
    )
    await session.commit()
