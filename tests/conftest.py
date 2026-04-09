"""
conftest.py — shared test configuration and fixtures.

Sets dummy env vars before any imports so pydantic-settings
never raises validation errors during testing.
All fixtures defined here are available to all test files
without needing to import them.
"""
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

os.environ.setdefault("OPENAI_API_KEY", "dummy-key-for-testing")
os.environ.setdefault("TAVILY_API_KEY", "")
os.environ.setdefault("GOOGLE_API_KEY", "")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGCHAIN_API_KEY", "")
os.environ.setdefault("LANGCHAIN_PROJECT", "test")


@pytest.fixture
def mock_app_client():
    """
    Creates a FastAPI TestClient with the LangGraph pipeline mocked.

    Patches BlogPipeline.build() so the lifespan never builds a real
    LangGraph graph or initializes a real ChatOpenAI instance.
    The mock blog_app.invoke returns a fake completed blog output.
    """
    # ✅ Mock the entire pipeline build — prevents real ChatOpenAI init
    mock_blog_app = MagicMock()
    mock_blog_app.invoke.return_value = {
        "plan": MagicMock(
            blog_title="Test Blog Post",
            blog_kind="explainer",
            tasks=[],
            model_dump=lambda: {
                "blog_title": "Test Blog Post",
                "blog_kind": "explainer",
                "audience": "developers",
                "tone": "practical",
                "tasks": [],
                "constraints": [],
            }
        ),
        "final": "# Test Blog Post\n\nThis is test content.",
        "image_specs": [],
        "evidence": [],
        "mode": "closed_book",
        "sections": [],
        "merged_md": "",
        "md_with_placeholders": "",
    }

    # ✅ Patch BlogPipeline.build before the app starts
    with patch("pipeline.blog_pipeline.BlogPipeline.build", return_value=mock_blog_app):
        from backend.main import app
        with TestClient(app) as client:
            yield client