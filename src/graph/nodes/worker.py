from __future__ import annotations

import sys
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Send
from src.logger import logging
from src.exception import MyException
from src.schemas.models import State, Task, Plan, EvidenceItem
from src.prompts.templates import WORKER_SYSTEM


def build_worker_node(llm: ChatOpenAI):
    """
    Factory that returns the worker_node function.

    Each worker instance writes one section of the blog post. Workers
    run in parallel via the fanout Send API. Each receives a payload
    with its specific task, the full plan for context, and evidence
    for grounded citations.

    The section is returned as a (task_id, section_md) tuple which
    gets appended to state['sections'] via the operator.add reducer,
    allowing all workers to write concurrently without overwriting
    each other.

    Args:
        llm: The ChatOpenAI instance used for writing.

    Returns:
        worker_node function compatible with StateGraph.add_node via Send.
    """
    def worker_node(payload: dict) -> dict:
        try:
            task = Task(**payload["task"])
            plan = Plan(**payload["plan"])
            evidence = [EvidenceItem(**e) for e in payload.get("evidence", [])]

            logging.info(f"Worker node — writing section '{task.title}' (id={task.id})")

            bullets_text = "\n- " + "\n- ".join(task.bullets)
            evidence_text = "\n".join(
                f"- {e.title} | {e.url} | {e.published_at or 'date:unknown'}"
                for e in evidence[:20]
            )

            section_md = llm.invoke([
                SystemMessage(content=WORKER_SYSTEM),
                HumanMessage(content=(
                    f"Blog title: {plan.blog_title}\n"
                    f"Audience: {plan.audience}\n"
                    f"Tone: {plan.tone}\n"
                    f"Blog kind: {plan.blog_kind}\n"
                    f"Constraints: {plan.constraints}\n"
                    f"Topic: {payload['topic']}\n"
                    f"Mode: {payload.get('mode')}\n"
                    f"As-of: {payload.get('as_of')} (recency_days={payload.get('recency_days')})\n\n"
                    f"Section title: {task.title}\n"
                    f"Goal: {task.goal}\n"
                    f"Target words: {task.target_words}\n"
                    f"Tags: {task.tags}\n"
                    f"requires_research: {task.requires_research}\n"
                    f"requires_citations: {task.requires_citations}\n"
                    f"requires_code: {task.requires_code}\n"
                    f"Bullets:{bullets_text}\n\n"
                    f"Evidence (ONLY cite these URLs):\n{evidence_text}\n"
                )),
            ]).content.strip()

            logging.info(f"Worker node — section '{task.title}' written ({len(section_md.split())} words)")
            return {"sections": [(task.id, section_md)]}

        except Exception as e:
            raise MyException(e, sys)

    return worker_node


def build_fanout(state: State):
    """
    Conditional edge function — dispatches one worker per task in parallel.

    Uses LangGraph's Send API to create independent worker invocations.
    Each Send carries a payload with the specific task, topic, mode,
    as_of, recency_days, full plan, and evidence list.

    Args:
        state: Current graph state with plan set by orchestrator_node.

    Returns:
        List of Send objects targeting the 'worker' node.

    Raises:
        AssertionError: If plan is None when fanout is called.
    """
    assert state["plan"] is not None, "fanout called without a plan in state"

    return [
        Send(
            "worker",
            {
                "task": task.model_dump(),
                "topic": state["topic"],
                "mode": state["mode"],
                "as_of": state["as_of"],
                "recency_days": state["recency_days"],
                "plan": state["plan"].model_dump(),
                "evidence": [e.model_dump() for e in state.get("evidence", [])],
            },
        )
        for task in state["plan"].tasks
    ]
