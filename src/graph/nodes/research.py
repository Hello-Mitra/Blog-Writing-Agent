from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.logger import logging
from src.exception import MyException
from src.schemas.models import State, EvidenceItem, EvidencePack
from src.prompts.templates import RESEARCH_SYSTEM
from src.research.tavily_search import tavily_search
from entity.config_entity import ResearchConfig


def _iso_to_date(s: Optional[str]) -> Optional[date]:
    """
    Safely parse an ISO date string to a date object.

    Args:
        s: ISO date string (YYYY-MM-DD) or None.

    Returns:
        date object if parseable, else None.
    """
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def build_research_node(llm: ChatOpenAI, config: ResearchConfig = None):
    """
    Factory that returns the research_node function.

    The research node runs after the router when needs_research=True.
    It:
    1. Runs all router-generated queries through Tavily search
    2. Passes raw results to the LLM for synthesis into EvidenceItems
    3. Deduplicates by URL
    4. Filters by recency if mode is open_book

    Args:
        llm   : The ChatOpenAI instance.
        config: ResearchConfig with max_results and max_queries settings.

    Returns:
        research_node function compatible with StateGraph.add_node.
    """
    if config is None:
        config = ResearchConfig()

    extractor = llm.with_structured_output(EvidencePack)

    def research_node(state: State) -> dict:
        try:
            queries = (state.get("queries") or [])[:config.max_queries]
            logging.info(f"Research node — running {len(queries)} queries")

            raw: List[dict] = []
            for q in queries:
                raw.extend(tavily_search(q, max_results=config.max_results_per_query))

            if not raw:
                logging.warning("Research node — no results from Tavily, returning empty evidence")
                return {"evidence": []}

            logging.info(f"Research node — synthesizing {len(raw)} raw results")

            pack = extractor.invoke([
                SystemMessage(content=RESEARCH_SYSTEM),
                HumanMessage(content=(
                    f"As-of date: {state['as_of']}\n"
                    f"Recency days: {state['recency_days']}\n\n"
                    f"Raw results:\n{raw}"
                )),
            ])

            # Deduplicate by URL
            dedup = {}
            for e in pack.evidence:
                if e.url:
                    dedup[e.url] = e
            evidence = list(dedup.values())

            # Filter by recency for open_book mode
            if state.get("mode") == "open_book":
                as_of = date.fromisoformat(state["as_of"])
                cutoff = as_of - timedelta(days=int(state["recency_days"]))
                evidence = [
                    e for e in evidence
                    if (d := _iso_to_date(e.published_at)) and d >= cutoff
                ]
                logging.info(f"Research node — after recency filter: {len(evidence)} evidence items")

            logging.info(f"Research node — final evidence count: {len(evidence)}")
            return {"evidence": evidence}

        except Exception as e:
            raise MyException(e, sys)

    return research_node
