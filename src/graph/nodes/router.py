from __future__ import annotations

import sys
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.logger import logging
from src.exception import MyException
from src.schemas.models import State, RouterDecision
from src.prompts.templates import ROUTER_SYSTEM
from entity.config_entity import LLMConfig


def build_router_node(llm: ChatOpenAI):
    """
    Factory that returns the router_node function bound to the given LLM.

    The router node is the first node in the graph. It reads the topic
    and as_of date from state and decides whether web research is needed
    before planning. It produces mode, needs_research, queries, and
    recency_days which are stored in state for downstream nodes.

    Args:
        llm: The ChatOpenAI instance to use for routing decisions.

    Returns:
        router_node function compatible with StateGraph.add_node.
    """
    decider = llm.with_structured_output(RouterDecision)

    def router_node(state: State) -> dict:
        try:
            logging.info(f"Router node — topic='{state['topic'][:60]}'")

            decision = decider.invoke([
                SystemMessage(content=ROUTER_SYSTEM),
                HumanMessage(content=f"Topic: {state['topic']}\nAs-of date: {state['as_of']}"),
            ])

            recency_days = {
                "open_book": 7,
                "hybrid": 45,
                "closed_book": 3650,
            }.get(decision.mode, 3650)

            logging.info(f"Router decision — mode={decision.mode}, needs_research={decision.needs_research}, queries={len(decision.queries)}")

            return {
                "needs_research": decision.needs_research,
                "mode": decision.mode,
                "queries": decision.queries,
                "recency_days": recency_days,
            }
        except Exception as e:
            raise MyException(e, sys)

    return router_node


def route_next(state: State) -> str:
    """
    Conditional edge function — routes to research or orchestrator.

    Called after router_node completes. If research is needed the
    graph goes to the research node first. Otherwise it skips directly
    to the orchestrator.

    Args:
        state: Current graph state with needs_research set by router_node.

    Returns:
        'research' if needs_research is True, else 'orchestrator'.
    """
    return "research" if state["needs_research"] else "orchestrator"
