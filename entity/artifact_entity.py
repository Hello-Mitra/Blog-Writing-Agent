from dataclasses import dataclass
from typing import Any, List


@dataclass
class BlogArtifact:
    """Final artifact produced by the pipeline."""
    blog_title: str
    final_md: str
    md_filename: str
    images_dir: str
    image_count: int
