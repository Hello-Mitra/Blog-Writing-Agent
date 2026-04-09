from __future__ import annotations

import sys
from typing import List
from src.logger import logging
from config.settings import settings


def tavily_search(query: str, max_results: int = 5) -> List[dict]:
    """
    Performs a single Tavily web search query and returns raw results.

    Returns an empty list if TAVILY_API_KEY is not set or if the
    search fails for any reason — allowing the pipeline to continue
    gracefully in closed_book mode without a key.

    Args:
        query      : The search query string.
        max_results: Maximum number of results to return.

    Returns:
        List of dicts with keys: title, url, snippet, published_at, source.
    """
    if not settings.tavily_api_key:
        logging.warning("TAVILY_API_KEY not set — skipping search")
        return []
    try:
        from langchain_community.tools.tavily_search import TavilySearchResults
        tool = TavilySearchResults(max_results=max_results)
        results = tool.invoke({"query": query})
        out: List[dict] = []
        for r in results or []:
            out.append({
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "snippet": r.get("content") or r.get("snippet") or "",
                "published_at": r.get("published_date") or r.get("published_at"),
                "source": r.get("source"),
            })
        logging.info(f"Tavily search '{query[:60]}' returned {len(out)} results")
        return out
    except Exception as e:
        logging.warning(f"Tavily search failed for query '{query[:60]}': {e}")
        return []
