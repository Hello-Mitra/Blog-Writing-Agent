from __future__ import annotations

import sys
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.logger import logging
from src.exception import MyException
from src.schemas.models import State, Plan
from src.prompts.templates import ORCHESTRATOR_SYSTEM


def build_orchestrator_node(llm: ChatOpenAI):
    """
    Factory that returns the orchestrator_node function.

    The orchestrator node generates the complete blog plan. It receives
    the topic, mode, as_of date, recency_days, and any evidence from the
    research node. It produces a Plan with 5-9 Task objects, one per
    section of the blog.

    For open_book mode, blog_kind is forced to 'news_roundup' after
    generation to ensure the LLM constraint is always respected.

    Args:
        llm: The ChatOpenAI instance used for planning.

    Returns:
        orchestrator_node function compatible with StateGraph.add_node.
    """
    planner = llm.with_structured_output(Plan)

    def orchestrator_node(state: State) -> dict:
        try:
            mode = state.get("mode", "closed_book")
            evidence = state.get("evidence", [])
            forced_kind = "news_roundup" if mode == "open_book" else None

            logging.info(f"Orchestrator node — mode={mode}, evidence_count={len(evidence)}")

            plan = planner.invoke([
                SystemMessage(content=ORCHESTRATOR_SYSTEM),
                HumanMessage(content=(
                    f"Topic: {state['topic']}\n"
                    f"Mode: {mode}\n"
                    f"As-of: {state['as_of']} (recency_days={state['recency_days']})\n"
                    f"{'Force blog_kind=news_roundup' if forced_kind else ''}\n\n"
                    f"Evidence:\n{[e.model_dump() for e in evidence][:16]}"
                )),
            ])

            # Always enforce news_roundup for open_book regardless of LLM output
            if forced_kind:
                plan.blog_kind = "news_roundup"

            logging.info(f"Orchestrator node — plan created: '{plan.blog_title}', {len(plan.tasks)} tasks, kind={plan.blog_kind}")
            return {"plan": plan}

        except Exception as e:
            raise MyException(e, sys)

    return orchestrator_node
