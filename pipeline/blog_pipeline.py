from __future__ import annotations

import sys
from src.logger import logging
from src.exception import MyException
from src.schemas.models import State
from src.graph.nodes.router import build_router_node, route_next
from src.graph.nodes.research import build_research_node
from src.graph.nodes.orchestrator import build_orchestrator_node
from src.graph.nodes.worker import build_worker_node, build_fanout
from src.graph.nodes.reducer import (
    build_merge_content_node,
    build_decide_images_node,
    build_generate_and_place_images_node,
)
from entity.config_entity import LLMConfig, ResearchConfig, OutputConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END


class BlogPipeline:
    """
    Builds and compiles the complete Blog Writing Agent LangGraph graph.

    Architecture:
        START
          → router (decides mode + research need)
          → [research] (optional, only if needs_research=True)
          → orchestrator (generates Plan with Tasks)
          → fanout → worker(s) [parallel, one per Task]
          → reducer subgraph:
              merge_content → decide_images → generate_and_place_images
          → END

    The reducer subgraph is compiled separately and embedded as a node
    in the main graph so LangGraph treats it as a single atomic step.

    Usage:
        pipeline = BlogPipeline()
        app = pipeline.build()
        out = app.invoke({"topic": "...", "as_of": "2026-04-09", ...})
    """

    def __init__(self):
        self.llm_config      = LLMConfig()
        self.research_config = ResearchConfig()
        self.output_config   = OutputConfig()

    def _build_reducer_subgraph(self, llm: ChatOpenAI):
        """
        Compiles the reducer subgraph:
            merge_content → decide_images → generate_and_place_images

        Returns:
            Compiled reducer subgraph ready to be embedded as a node.
        """
        reducer = StateGraph(State)
        reducer.add_node("merge_content",               build_merge_content_node())
        reducer.add_node("decide_images",               build_decide_images_node(llm))
        reducer.add_node("generate_and_place_images",   build_generate_and_place_images_node(self.output_config))
        reducer.add_edge(START, "merge_content")
        reducer.add_edge("merge_content", "decide_images")
        reducer.add_edge("decide_images", "generate_and_place_images")
        reducer.add_edge("generate_and_place_images", END)
        return reducer.compile()

    def build(self):
        """
        Builds and compiles the full Blog Writing Agent graph.

        Returns:
            Compiled LangGraph app ready for .invoke() or .stream().
        """
        try:
            logging.info("Building BlogPipeline")

            llm = ChatOpenAI(model=self.llm_config.model_name)

            reducer_subgraph = self._build_reducer_subgraph(llm)

            g = StateGraph(State)
            g.add_node("router",       build_router_node(llm))
            g.add_node("research",     build_research_node(llm, self.research_config))
            g.add_node("orchestrator", build_orchestrator_node(llm))
            g.add_node("worker",       build_worker_node(llm))
            g.add_node("reducer",      reducer_subgraph)

            g.add_edge(START, "router")
            g.add_conditional_edges(
                "router", route_next,
                {"research": "research", "orchestrator": "orchestrator"}
            )
            g.add_edge("research", "orchestrator")
            g.add_conditional_edges("orchestrator", build_fanout, ["worker"])
            g.add_edge("worker", "reducer")
            g.add_edge("reducer", END)

            app = g.compile()
            logging.info("BlogPipeline built successfully")
            return app

        except Exception as e:
            raise MyException(e, sys)
