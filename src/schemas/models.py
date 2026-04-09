from __future__ import annotations

import operator
from typing import TypedDict, List, Optional, Literal, Annotated
from pydantic import BaseModel, Field


# ── Task ─────────────────────────────────────────────────────────────────────

class Task(BaseModel):
    """
    Represents one section of the blog post.

    Each Task is dispatched to an individual worker node for parallel
    content generation. The combination of goal, bullets, target_words
    and flags gives the worker precise instructions.

    Attributes:
        id                : Section order — used to sort sections in reducer.
        title             : Short section name.
        goal              : One sentence outcome for the reader.
        bullets           : 3-6 concrete content points to cover.
        target_words      : Word count target (120-550).
        tags              : Flexible topic labels for the section.
        requires_research : True if this section needs evidence grounding.
        requires_citations: True if inline URL citations are needed.
        requires_code     : True if a code snippet should be included.
    """
    id: int
    title: str
    goal: str = Field(..., description="One sentence describing what the reader should do/understand.")
    bullets: List[str] = Field(..., min_length=3, max_length=6)
    target_words: int = Field(..., description="Target words (120-550).")
    tags: List[str] = Field(default_factory=list)
    requires_research: bool = False
    requires_citations: bool = False
    requires_code: bool = False


# ── Plan ─────────────────────────────────────────────────────────────────────

class Plan(BaseModel):
    """
    The complete blog plan produced by the orchestrator node.

    Stored in State and passed to every worker so each worker has
    full context of the overall blog structure, audience, and tone.

    Attributes:
        blog_title  : Title of the full blog post.
        audience    : Who the blog is written for.
        tone        : Writing style (e.g. practical, academic).
        blog_kind   : Type of blog — affects worker behaviour.
        constraints : Global writing constraints applied to all sections.
        tasks       : Ordered list of Task objects, one per section.
    """
    blog_title: str
    audience: str
    tone: str
    blog_kind: Literal["explainer", "tutorial", "news_roundup", "comparison", "system_design"] = "explainer"
    constraints: List[str] = Field(default_factory=list)
    tasks: List[Task]


# ── Research ──────────────────────────────────────────────────────────────────

class EvidenceItem(BaseModel):
    """
    A single piece of web evidence returned by the research node.

    Attributes:
        title        : Page or article title.
        url          : Source URL — workers cite this in markdown links.
        published_at : ISO YYYY-MM-DD if reliably known, else None.
        snippet      : Short extract from the source.
        source       : Domain or publication name.
    """
    title: str
    url: str
    published_at: Optional[str] = None
    snippet: Optional[str] = None
    source: Optional[str] = None


class EvidencePack(BaseModel):
    """Wrapper returned by LLM structured output for research synthesis."""
    evidence: List[EvidenceItem] = Field(default_factory=list)


class RouterDecision(BaseModel):
    """
    The routing decision produced by the router node.

    Determines whether web research is needed before planning and
    how recent the evidence needs to be.

    Attributes:
        needs_research       : Whether to run the research node.
        mode                 : closed_book / hybrid / open_book.
        reason               : Brief explanation for the decision.
        queries              : Search queries if needs_research=True.
        max_results_per_query: Tavily results per query.
    """
    needs_research: bool
    mode: Literal["closed_book", "hybrid", "open_book"]
    reason: str
    queries: List[str] = Field(default_factory=list)
    max_results_per_query: int = Field(5)


# ── Image Planning ────────────────────────────────────────────────────────────

class ImageSpec(BaseModel):
    """
    Specification for one AI-generated image.

    Attributes:
        placeholder : Markdown placeholder token e.g. [[IMAGE_1]].
        filename    : Save path under images/ directory.
        alt         : Image alt text for accessibility.
        caption     : Caption shown below the image.
        prompt      : Full text prompt sent to the image generation model.
        size        : Image dimensions.
        quality     : Generation quality level.
    """
    placeholder: str = Field(..., description="e.g. [[IMAGE_1]]")
    filename: str
    alt: str
    caption: str
    prompt: str
    # ✅ Only valid DALL-E 3 sizes
    size: Literal["1024x1024", "1024x1792", "1792x1024"] = "1024x1024"
    quality: Literal["low", "medium", "high"] = "medium"

class GlobalImagePlan(BaseModel):
    """
    The image plan returned by the decide_images node.

    Contains the full markdown with placeholders inserted and the
    list of image specs that need to be generated.
    """
    md_with_placeholders: str
    images: List[ImageSpec] = Field(default_factory=list)


# ── Graph State ───────────────────────────────────────────────────────────────

class State(TypedDict):
    """
    The shared LangGraph state that flows through the entire graph.

    Attributes:
        topic                 : User-provided blog topic.
        mode                  : Routing mode (closed_book/hybrid/open_book).
        needs_research        : Whether research node was triggered.
        queries               : Search queries from router.
        evidence              : Evidence items from research node.
        plan                  : Blog plan from orchestrator.
        as_of                 : ISO date string for recency grounding.
        recency_days          : How many days back evidence must be.
        sections              : (task_id, section_md) tuples from workers.
                                Uses operator.add for parallel fan-out.
        merged_md             : Full markdown after sections are joined.
        md_with_placeholders  : Markdown with [[IMAGE_N]] placeholders.
        image_specs           : List of image spec dicts.
        final                 : Final markdown with images embedded or fallbacks.
    """
    topic: str
    mode: str
    needs_research: bool
    queries: List[str]
    evidence: List[EvidenceItem]
    plan: Optional[Plan]
    as_of: str
    recency_days: int
    sections: Annotated[List[tuple], operator.add]
    merged_md: str
    md_with_placeholders: str
    image_specs: List[dict]
    final: str
