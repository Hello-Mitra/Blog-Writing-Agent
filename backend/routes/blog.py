from __future__ import annotations

import sys
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from src.logger import logging
from src.exception import MyException
from src.schemas.requests import (
    GenerateRequest, GenerateResponse,
    BlogListResponse, BlogListItem, BlogContentResponse,
)
from src.tools.slug import safe_slug
from config.settings import settings

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
def generate_blog(request: Request, body: GenerateRequest):
    """
    Generate a complete blog post for the given topic and as_of date.
    Invokes the full LangGraph pipeline synchronously.
    """
    try:
        logging.info(f"Generate request — topic='{body.topic[:60]}', as_of={body.as_of}")

        app = request.app.state.blog_app

        inputs = {
            "topic": body.topic.strip(),
            "mode": "",
            "needs_research": False,
            "queries": [],
            "evidence": [],
            "plan": None,
            "as_of": body.as_of,
            "recency_days": 7,
            "sections": [],
            "merged_md": "",
            "md_with_placeholders": "",
            "image_specs": [],
            "final": "",
        }

        out = app.invoke(inputs)

        plan = out.get("plan")
        blog_title = plan.blog_title if plan else "Blog"
        final_md = out.get("final", "")
        image_specs = out.get("image_specs") or []
        mode = out.get("mode", "closed_book")
        md_filename = f"{safe_slug(blog_title)}.md"

        logging.info(f"Generate complete — '{blog_title}', {len(image_specs)} images, mode={mode}")

        return GenerateResponse(
            blog_title=blog_title,
            final_md=final_md,
            md_filename=md_filename,
            image_count=len(image_specs),
            mode=mode,
        )

    except Exception as e:
        logging.error(f"Generate error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(MyException(e, sys)))


@router.post("/generate/stream")
def generate_blog_stream(request: Request, body: GenerateRequest):
    """
    Stream graph progress events via SSE while generating a blog.

    Yields SSE events:
    - node    : {"type": "node",    "name": "<node_name>"}
    - summary : {"type": "summary", "data": {...}}
    - done    : {"type": "done",    "final_md": "...", "blog_title": "...",
                                    "plan": {...}, "evidence": [...],
                                    "image_specs": [...], "mode": "..."}
    - error   : {"type": "error",   "content": "..."}
    """
    try:
        app = request.app.state.blog_app

        inputs = {
            "topic": body.topic.strip(),
            "mode": "",
            "needs_research": False,
            "queries": [],
            "evidence": [],
            "plan": None,
            "as_of": body.as_of,
            "recency_days": 7,
            "sections": [],
            "merged_md": "",
            "md_with_placeholders": "",
            "image_specs": [],
            "final": "",
        }

        def generate():
            try:
                final_state = {}
                last_node = None

                for step in app.stream(inputs, stream_mode="updates"):
                    if not isinstance(step, dict):
                        continue

                    node_name = next(iter(step.keys()), None)

                    # emit node name event
                    if node_name and node_name != last_node:
                        yield f"data: {json.dumps({'type': 'node', 'name': node_name})}\n\n"
                        last_node = node_name

                    # accumulate state
                    inner = step.get(node_name, {})
                    if isinstance(inner, dict):
                        final_state.update(inner)

                    # emit progress summary
                    plan_obj = final_state.get("plan")
                    summary = {
                        "mode": final_state.get("mode"),
                        "needs_research": final_state.get("needs_research"),
                        "queries": (final_state.get("queries") or [])[:5],
                        "evidence_count": len(final_state.get("evidence") or []),
                        "tasks": (
                            len(plan_obj.tasks)
                            if plan_obj and hasattr(plan_obj, "tasks")
                            else None
                        ),
                        "sections_done": len(final_state.get("sections") or []),
                        "images": len(final_state.get("image_specs") or []),
                    }
                    yield f"data: {json.dumps({'type': 'summary', 'data': summary}, default=str)}\n\n"

                # ── Build done event with full plan + evidence ──────────────
                plan_obj = final_state.get("plan")

                plan_dict = None
                if plan_obj:
                    if hasattr(plan_obj, "model_dump"):
                        plan_dict = plan_obj.model_dump()
                    elif isinstance(plan_obj, dict):
                        plan_dict = plan_obj

                evidence_list = []
                for e in (final_state.get("evidence") or []):
                    if hasattr(e, "model_dump"):
                        evidence_list.append(e.model_dump())
                    elif isinstance(e, dict):
                        evidence_list.append(e)

                blog_title = (
                    plan_obj.blog_title
                    if plan_obj and hasattr(plan_obj, "blog_title")
                    else "Blog"
                )

                done_payload = {
                    "type": "done",
                    "final_md": final_state.get("final", ""),
                    "blog_title": blog_title,
                    "mode": final_state.get("mode", ""),
                    "image_count": len(final_state.get("image_specs") or []),
                    "plan": plan_dict,
                    "evidence": evidence_list,
                    "image_specs": final_state.get("image_specs") or [],
                }
                yield f"data: {json.dumps(done_payload, default=str)}\n\n"

            except Exception as e:
                logging.error(f"Stream error: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        logging.error(f"Stream setup error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(MyException(e, sys)))


@router.get("/blogs", response_model=BlogListResponse)
def list_blogs():
    """
    Return all generated blog .md files from output_dir.
    Sorted newest-first. Returns up to 50 blogs.
    """
    try:
        output_dir = Path(settings.output_dir)
        if not output_dir.exists():
            return BlogListResponse(blogs=[])

        files = sorted(
            [p for p in output_dir.glob("*.md") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:50]

        blogs = []
        for p in files:
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                title = next(
                    (line[2:].strip() for line in content.splitlines() if line.startswith("# ")),
                    p.stem,
                )
                modified_at = datetime.fromtimestamp(p.stat().st_mtime).isoformat()
                blogs.append(BlogListItem(
                    filename=p.name,
                    title=title,
                    modified_at=modified_at,
                ))
            except Exception:
                pass

        return BlogListResponse(blogs=blogs)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(MyException(e, sys)))


@router.get("/blogs/{filename}", response_model=BlogContentResponse)
def get_blog(filename: str):
    """
    Return markdown content of a specific blog file.
    """
    try:
        output_dir = Path(settings.output_dir)
        file_path = output_dir / filename

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail=f"Blog '{filename}' not found.")

        content = file_path.read_text(encoding="utf-8", errors="replace")
        return BlogContentResponse(filename=filename, content=content)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(MyException(e, sys)))