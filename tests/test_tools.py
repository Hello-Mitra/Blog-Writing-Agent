"""
Unit tests for utility tools.

Tests safe_slug and tavily_search in isolation.
No LLM calls or external API calls are made.
"""
import pytest
from unittest.mock import patch, MagicMock
from src.tools.slug import safe_slug


class TestSafeSlug:
    """Unit tests for the safe_slug utility function."""

    def test_basic_title(self):
        """Simple title converts to lowercase underscored slug."""
        assert safe_slug("Hello World") == "hello_world"

    def test_title_with_special_chars(self):
        """Special characters like colons are removed."""
        assert safe_slug("AI: The Future") == "ai_the_future"

    def test_title_with_multiple_spaces(self):
        """Multiple spaces are collapsed to single underscore."""
        assert safe_slug("Too  Many   Spaces") == "too_many_spaces"

    def test_empty_string_fallback(self):
        """Empty string falls back to 'blog'."""
        assert safe_slug("") == "blog"

    def test_all_special_chars_fallback(self):
        """String of only special chars falls back to 'blog'."""
        assert safe_slug("!!!???###") == "blog"

    def test_already_lowercase(self):
        """Already lowercase title stays correct."""
        assert safe_slug("my blog post") == "my_blog_post"

    def test_long_title_with_colon(self):
        """Realistic blog title with colon converts correctly."""
        result = safe_slug("The Impact of AI: What You Need to Know")
        assert result == "the_impact_of_ai_what_you_need_to_know"
        assert ":" not in result

    def test_numbers_preserved(self):
        """Numbers in title are preserved."""
        assert safe_slug("Top 10 Python Tips") == "top_10_python_tips"


class TestTavilySearch:
    """Unit tests for the tavily_search function."""

    def test_returns_empty_list_without_api_key(self):
        """
        tavily_search returns an empty list when TAVILY_API_KEY is not set.
        This ensures the pipeline degrades gracefully in closed_book mode.
        """
        from src.research.tavily_search import tavily_search
        from config.settings import settings

        original = settings.tavily_api_key
        settings.tavily_api_key = ""

        result = tavily_search("test query")
        assert result == []

        settings.tavily_api_key = original

    def test_returns_list_on_success(self):
        """
        tavily_search returns a list of dicts on successful API response.
        The actual API call is mocked.
        """
        from src.research.tavily_search import tavily_search
        from config.settings import settings

        settings.tavily_api_key = "fake-key"

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = [
            {"title": "Test Article", "url": "https://example.com", "content": "Summary here."}
        ]

        with patch("src.research.tavily_search.TavilySearchResults", return_value=mock_tool):
            result = tavily_search("test query", max_results=3)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com"

        settings.tavily_api_key = ""

    def test_returns_empty_list_on_exception(self):
        """
        tavily_search returns empty list when an exception is raised.
        This verifies graceful degradation on network errors.
        """
        from src.research.tavily_search import tavily_search
        from config.settings import settings

        settings.tavily_api_key = "fake-key"

        with patch("src.research.tavily_search.TavilySearchResults", side_effect=Exception("Network error")):
            result = tavily_search("test query")

        assert result == []
        settings.tavily_api_key = ""
