from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.logger import logging
from src.exception import MyException
from pipeline.blog_pipeline import BlogPipeline
from backend.routes import blog

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build and cache the LangGraph app once on startup."""
    try:
        logging.info("Starting Blog Writing Agent API")
        pipeline = BlogPipeline()
        blog_app = pipeline.build()
        app.state.blog_app = blog_app
        logging.info("API startup complete — blog_app ready")
        yield
    except Exception as e:
        raise MyException(e, sys)
    finally:
        logging.info("API shutting down")


app = FastAPI(
    title="Blog Writing Agent API",
    description="LangGraph blog writing agent with research, planning, parallel workers, and AI image generation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(blog.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
