from pydantic import BaseModel
from typing import Any, Optional


class GenerateRequest(BaseModel):
    """Request body for POST /api/generate."""
    topic: str
    as_of: str  # ISO date string YYYY-MM-DD


class GenerateResponse(BaseModel):
    """Response body for POST /api/generate."""
    blog_title: str
    final_md: str
    md_filename: str
    image_count: int
    mode: str


class BlogListItem(BaseModel):
    """One item in the GET /api/blogs response."""
    filename: str
    title: str
    modified_at: str


class BlogListResponse(BaseModel):
    """Response body for GET /api/blogs."""
    blogs: list[BlogListItem]


class BlogContentResponse(BaseModel):
    """Response body for GET /api/blogs/{filename}."""
    filename: str
    content: str
