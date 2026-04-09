from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    openai_api_key: str
    model_name: str = "gpt-4.1-mini"
    tavily_api_key: str = ""
    google_api_key: str = ""

    output_dir: str = "artifacts/blogs"
    images_dir: str = "artifacts/images"

    langchain_tracing_v2: str = "false"
    langchain_api_key: str = ""
    langchain_project: str = "BlogWritingAgent"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
