from __future__ import annotations

import sys
import base64
import re
from src.logger import logging
from src.exception import MyException
from config.settings import settings


def _sanitize_prompt(prompt: str) -> str:
    """
    Sanitizes image prompt to reduce content policy violations.

    Removes specific model/company names that trigger OpenAI safety filters
    and replaces them with generic descriptions. Keeps the visual intent intact.
    """
    # Remove specific AI model/company names that trigger safety filters
    replacements = [
        (r'\bDeepSeek[-\s]?R\d+\b', 'a reasoning LLM'),
        (r'\bQwen\d*[-\s]?\w*\b', 'a multilingual LLM'),
        (r'\bGemini\s+Embedding\s+\w+\b', 'an embedding model'),
        (r'\bGPT-\d+\w*\b', 'a large language model'),
        (r'\bClaude\s+\w+\b', 'a large language model'),
        (r'\bLlama\s*\d*\w*\b', 'an open source LLM'),
        (r'\bMistral\s*\w*\b', 'an open source LLM'),
    ]
    sanitized = prompt
    for pattern, replacement in replacements:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    return sanitized


def generate_image_bytes(prompt: str, size: str = "1024x1024", quality: str = "standard") -> bytes:
    """
    Generates an image using OpenAI DALL-E 3 and returns raw PNG bytes.

    Automatically sanitizes the prompt to reduce content policy violations.
    If the sanitized prompt still fails, raises MyException with the error.

    Args:
        prompt  : Image generation prompt.
        size    : Image dimensions — 1024x1024, 1792x1024, 1024x1792.
        quality : 'standard' (cheaper) or 'hd' (better).

    Returns:
        Raw PNG bytes.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)

        # ✅ Normalize size — DALL-E 3 only supports these three values
        VALID_SIZES = {"1024x1024", "1024x1792", "1792x1024"}
        SIZE_FALLBACK = {
            "1536x1024": "1792x1024",   # wider → use closest valid wide
            "1024x1536": "1024x1792",   # taller → use closest valid tall
        }
        normalized_size = SIZE_FALLBACK.get(size, size)
        if normalized_size not in VALID_SIZES:
            normalized_size = "1024x1024"  # safe default for any unknown value

        if normalized_size != size:
            logging.info(f"Size '{size}' normalized to '{normalized_size}' for DALL-E 3")

        sanitized_prompt = _sanitize_prompt(prompt)
        logging.info(f"Generating image — size={normalized_size}, prompt: {sanitized_prompt[:80]}")

        response = client.images.generate(
            model="dall-e-3",
            prompt=sanitized_prompt,
            size=normalized_size,
            quality=quality,
            response_format="b64_json",
            n=1,
        )

        image_bytes = base64.b64decode(response.data[0].b64_json)
        logging.info("Image generated successfully")
        return image_bytes

    except Exception as e:
        raise MyException(e, sys)