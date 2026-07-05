"""Exa search integration — used as a tool by the LLM."""

from __future__ import annotations

from exa_py import Exa

from app.config import settings

_client: Exa | None = None


def _get_client() -> Exa:
    global _client
    if _client is None:
        _client = Exa(api_key=settings.exa_api_key)
    return _client


def search(query: str, num_results: int = 5) -> list[dict]:
    """Run an Exa search and return simplified results for LLM context."""
    client = _get_client()
    results = client.search(
        query,
        type="auto",
        num_results=num_results,
        contents={"highlights": True},
    )
    out = []
    for r in results.results:
        out.append({
            "title": r.title,
            "url": r.url,
            "highlights": r.highlights if hasattr(r, "highlights") else [],
        })
    return out
