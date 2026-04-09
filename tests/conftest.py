"""
conftest.py — shared test configuration and fixtures.

Sets dummy env vars before any imports so pydantic-settings
never raises validation errors during testing.
All fixtures defined here are available to all test files
without needing to import them.
"""
import os
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# Set dummy env vars BEFORE anything imports settings
os.environ.setdefault("OPENAI_API_KEY", "dummy-key-for-testing")
os.environ.setdefault("TAVILY_API_KEY", "")
os.environ.setdefault("GOOGLE_API_KEY", "")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGCHAIN_API_KEY", "")
os.environ.setdefault("LANGCHAIN_PROJECT", "test")


@pytest.fixture
def mock_app_client():
    """
    Creates a FastAPI TestClient with mocked app.state.blog_app.

    The LangGraph app is mocked so API tests never make real LLM
    calls or generate real blog content.

    Yields a TestClient ready for use in test methods.
    """
    from backend.main import app

    mock_blog_app = MagicMock()
    mock_blog_app.invoke.return_value = {
        "plan": MagicMock(
            blog_title="Test Blog Post",
            blog_kind="explainer",
            tasks=[],
        ),
        "final": "# Test Blog Post\n\nThis is test content.",
        "image_specs": [],
        "evidence": [],
        "mode": "closed_book",
    }

    app.state.blog_app = mock_blog_app

    with TestClient(app) as client:
        yield client
