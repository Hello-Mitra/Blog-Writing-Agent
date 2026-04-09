"""
Unit tests for Pydantic schema models.

These tests verify that the core data models validate correctly,
reject invalid inputs, and apply defaults as expected.
No LLM calls — pure data validation tests.
"""
import pytest
from src.schemas.models import Task, Plan, EvidenceItem, RouterDecision


class TestTaskSchema:
    """Unit tests for the Task model."""

    def test_task_creates_successfully(self):
        """Task creates with valid inputs."""
        task = Task(
            id=1,
            title="Introduction",
            goal="Reader understands the topic.",
            bullets=["Point one", "Point two", "Point three"],
            target_words=200,
        )
        assert task.id == 1
        assert task.title == "Introduction"
        assert task.target_words == 200

    def test_task_defaults_are_false(self):
        """Task boolean flags default to False."""
        task = Task(
            id=1,
            title="Section",
            goal="Goal here.",
            bullets=["a", "b", "c"],
            target_words=150,
        )
        assert task.requires_research is False
        assert task.requires_citations is False
        assert task.requires_code is False

    def test_task_tags_default_to_empty_list(self):
        """Task tags default to an empty list."""
        task = Task(
            id=1,
            title="Section",
            goal="Goal here.",
            bullets=["a", "b", "c"],
            target_words=150,
        )
        assert task.tags == []

    def test_task_rejects_too_few_bullets(self):
        """Task raises validation error when fewer than 3 bullets provided."""
        with pytest.raises(Exception):
            Task(
                id=1,
                title="Section",
                goal="Goal.",
                bullets=["only one bullet"],
                target_words=150,
            )

    def test_task_rejects_too_many_bullets(self):
        """Task raises validation error when more than 6 bullets provided."""
        with pytest.raises(Exception):
            Task(
                id=1,
                title="Section",
                goal="Goal.",
                bullets=["a", "b", "c", "d", "e", "f", "g"],
                target_words=150,
            )


class TestPlanSchema:
    """Unit tests for the Plan model."""

    def test_plan_creates_successfully(self):
        """Plan creates with valid inputs."""
        plan = Plan(
            blog_title="Test Blog",
            audience="developers",
            tone="practical",
            tasks=[
                Task(id=1, title="Intro", goal="Goal.", bullets=["a", "b", "c"], target_words=150)
            ],
        )
        assert plan.blog_title == "Test Blog"
        assert len(plan.tasks) == 1

    def test_plan_default_blog_kind(self):
        """Plan defaults to explainer blog_kind."""
        plan = Plan(
            blog_title="Test",
            audience="devs",
            tone="casual",
            tasks=[
                Task(id=1, title="S", goal="G.", bullets=["a", "b", "c"], target_words=100)
            ],
        )
        assert plan.blog_kind == "explainer"

    def test_plan_constraints_default_empty(self):
        """Plan constraints default to empty list."""
        plan = Plan(
            blog_title="Test",
            audience="devs",
            tone="casual",
            tasks=[
                Task(id=1, title="S", goal="G.", bullets=["a", "b", "c"], target_words=100)
            ],
        )
        assert plan.constraints == []


class TestEvidenceItemSchema:
    """Unit tests for the EvidenceItem model."""

    def test_evidence_creates_with_required_fields(self):
        """EvidenceItem creates with title and url."""
        item = EvidenceItem(title="Test Article", url="https://example.com")
        assert item.title == "Test Article"
        assert item.url == "https://example.com"

    def test_evidence_optional_fields_default_none(self):
        """Optional fields default to None."""
        item = EvidenceItem(title="Test", url="https://example.com")
        assert item.published_at is None
        assert item.snippet is None
        assert item.source is None


class TestRouterDecisionSchema:
    """Unit tests for the RouterDecision model."""

    def test_router_decision_closed_book(self):
        """RouterDecision creates for closed_book mode."""
        decision = RouterDecision(
            needs_research=False,
            mode="closed_book",
            reason="Evergreen topic.",
        )
        assert decision.needs_research is False
        assert decision.mode == "closed_book"
        assert decision.queries == []

    def test_router_decision_open_book(self):
        """RouterDecision creates for open_book mode with queries."""
        decision = RouterDecision(
            needs_research=True,
            mode="open_book",
            reason="News topic.",
            queries=["AI news this week", "latest LLM releases"],
        )
        assert decision.needs_research is True
        assert len(decision.queries) == 2
