"""
Unit tests for utility tools.

Tests safe_slug and tavily_search in isolation.
No LLM calls or external API calls are made.
"""

from unittest.mock import patch, MagicMock
from src.tools.slug import safe_slug


class TestTavilySearch:

    def test_returns_empty_list_without_api_key(self):
        """Returns empty list when TAVILY_API_KEY is not set."""
        from src.research.tavily_search import tavily_search
        from config.settings import settings

        original = settings.tavily_api_key
        settings.tavily_api_key = ""
        result = tavily_search("test query")
        assert result == []
        settings.tavily_api_key = original

    def test_returns_list_on_success(self):
        """Returns list of dicts on successful API response."""
        from src.research.tavily_search import tavily_search
        from config.settings import settings

        settings.tavily_api_key = "fake-key"

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = [
            {"title": "Test Article", "url": "https://example.com", "content": "Summary."}
        ]

        # ✅ Patch at the source location, not the module-level import
        with patch("langchain_community.tools.tavily_search.TavilySearchResults", return_value=mock_tool):
            result = tavily_search("test query", max_results=3)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com"

        settings.tavily_api_key = ""

    def test_returns_empty_list_on_exception(self):
        """Returns empty list when an exception is raised."""
        from src.research.tavily_search import tavily_search
        from config.settings import settings

        settings.tavily_api_key = "fake-key"

        # ✅ Patch at the source location
        with patch("langchain_community.tools.tavily_search.TavilySearchResults", side_effect=Exception("Network error")):
            result = tavily_search("test query")

        assert result == []
        settings.tavily_api_key = ""