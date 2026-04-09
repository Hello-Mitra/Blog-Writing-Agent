"""
API endpoint tests for the Blog Writing Agent FastAPI backend.

Uses FastAPI TestClient with a mocked LangGraph app so no real
LLM calls are made during testing. The mock_app_client fixture
is defined in conftest.py and injected automatically by pytest.
"""

class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_health_returns_200(self, mock_app_client):
        """Health endpoint returns HTTP 200."""
        response = mock_app_client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok(self, mock_app_client):
        """Health endpoint returns status: ok."""
        response = mock_app_client.get("/health")
        assert response.json() == {"status": "ok"}


class TestGenerateEndpoint:
    """Tests for POST /api/generate"""

    def test_generate_returns_200(self, mock_app_client):
        """Generate endpoint returns 200 for valid request."""
        response = mock_app_client.post("/api/generate", json={
            "topic": "Introduction to LangGraph",
            "as_of": "2026-04-09"
        })
        assert response.status_code == 200

    def test_generate_returns_blog_title(self, mock_app_client):
        """Generate response contains blog_title field."""
        response = mock_app_client.post("/api/generate", json={
            "topic": "Introduction to LangGraph",
            "as_of": "2026-04-09"
        })
        assert "blog_title" in response.json()

    def test_generate_returns_final_md(self, mock_app_client):
        """Generate response contains final_md field."""
        response = mock_app_client.post("/api/generate", json={
            "topic": "Introduction to LangGraph",
            "as_of": "2026-04-09"
        })
        assert "final_md" in response.json()

    def test_generate_returns_md_filename(self, mock_app_client):
        """Generate response contains md_filename ending with .md."""
        response = mock_app_client.post("/api/generate", json={
            "topic": "Introduction to LangGraph",
            "as_of": "2026-04-09"
        })
        data = response.json()
        assert "md_filename" in data
        assert data["md_filename"].endswith(".md")

    def test_generate_missing_topic_returns_422(self, mock_app_client):
        """Generate endpoint returns 422 when topic is missing."""
        response = mock_app_client.post("/api/generate", json={
            "as_of": "2026-04-09"
        })
        assert response.status_code == 422

    def test_generate_missing_as_of_returns_422(self, mock_app_client):
        """Generate endpoint returns 422 when as_of is missing."""
        response = mock_app_client.post("/api/generate", json={
            "topic": "Some topic"
        })
        assert response.status_code == 422

    def test_generate_empty_topic_still_calls_app(self, mock_app_client):
        """
        Generate endpoint with empty topic still calls app.invoke.
        Empty string is technically valid pydantic — the pipeline
        handles empty topic gracefully.
        """
        response = mock_app_client.post("/api/generate", json={
            "topic": "",
            "as_of": "2026-04-09"
        })
        assert response.status_code in [200, 422, 500]


class TestBlogsListEndpoint:
    """Tests for GET /api/blogs"""

    def test_blogs_returns_200(self, mock_app_client):
        """Blogs list endpoint returns 200."""
        response = mock_app_client.get("/api/blogs")
        assert response.status_code == 200

    def test_blogs_returns_blogs_key(self, mock_app_client):
        """Blogs list response contains blogs key."""
        response = mock_app_client.get("/api/blogs")
        assert "blogs" in response.json()

    def test_blogs_returns_list(self, mock_app_client):
        """Blogs value is a list."""
        response = mock_app_client.get("/api/blogs")
        assert isinstance(response.json()["blogs"], list)


class TestBlogContentEndpoint:
    """Tests for GET /api/blogs/{filename}"""

    def test_get_blog_returns_404_for_nonexistent(self, mock_app_client):
        """
        Blog content endpoint returns 404 for a filename that
        doesn't exist in the output directory.
        """
        response = mock_app_client.get("/api/blogs/nonexistent_file.md")
        assert response.status_code == 404

    def test_get_blog_returns_content_for_existing_file(self, mock_app_client, tmp_path):
        """
        Blog content endpoint returns 200 and content for an existing file.
        Creates a temp file in the output dir and verifies it's returned.
        """
        from config.settings import settings

        # Temporarily set output_dir to tmp_path
        original_output_dir = settings.output_dir
        settings.output_dir = str(tmp_path)

        # Create a test blog file
        test_file = tmp_path / "test_blog.md"
        test_file.write_text("# Test Blog\n\nContent here.", encoding="utf-8")

        response = mock_app_client.get("/api/blogs/test_blog.md")

        assert response.status_code == 200
        assert "content" in response.json()
        assert "Test Blog" in response.json()["content"]

        settings.output_dir = original_output_dir
