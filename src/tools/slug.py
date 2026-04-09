from __future__ import annotations
import re


def safe_slug(title: str) -> str:
    """
    Converts a blog title to a safe filename slug.

    Removes special characters that are invalid in filenames
    (colons, quotes, slashes etc) and replaces spaces with underscores.

    Args:
        title: The raw blog title string.

    Returns:
        A lowercase underscore-separated slug safe for use as a filename.
        Falls back to 'blog' if the title produces an empty string.

    Example:
        "The Impact of AI: What You Need to Know"
        → "the_impact_of_ai_what_you_need_to_know"
    """
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9 _-]+", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s or "blog"
