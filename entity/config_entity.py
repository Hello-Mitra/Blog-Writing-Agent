from dataclasses import dataclass
from config.settings import settings


@dataclass
class LLMConfig:
    model_name: str = settings.model_name


@dataclass
class ResearchConfig:
    tavily_api_key: str = settings.tavily_api_key
    max_results_per_query: int = 6
    max_queries: int = 10
    max_evidence_items: int = 16


@dataclass
class ImageConfig:
    google_api_key: str = settings.google_api_key
    images_dir: str = settings.images_dir
    max_images: int = 3


@dataclass
class OutputConfig:
    output_dir: str = settings.output_dir
    images_dir: str = settings.images_dir
