from __future__ import annotations

import json
import os
import re
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests as http_requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="DeepDraft — Research-backed content generation", layout="wide")


# ── Helpers ───────────────────────────────────────────────────────────────────

def api_get(path: str) -> dict:
    resp = http_requests.get(f"{BACKEND_URL}{path}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def stream_generate(topic: str, as_of: str):
    """Stream SSE events from /api/generate/stream."""
    with http_requests.post(
        f"{BACKEND_URL}/api/generate/stream",
        json={"topic": topic, "as_of": as_of},
        stream=True,
        timeout=600,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                decoded = line.decode("utf-8")
                if decoded.startswith("data: "):
                    try:
                        yield json.loads(decoded[6:])
                    except json.JSONDecodeError:
                        pass


def safe_slug(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9 _-]+", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s or "blog"


def bundle_zip(md_text: str, md_filename: str) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(md_filename, md_text.encode("utf-8"))
        images_dir = Path("artifacts/images")
        if images_dir.exists():
            for p in images_dir.rglob("*"):
                if p.is_file():
                    z.write(p, arcname=str(p))
    return buf.getvalue()


def extract_title(md: str, fallback: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback


# ── Markdown renderer ─────────────────────────────────────────────────────────

_MD_IMG_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)")
_CAPTION_LINE_RE = re.compile(r"^\*(?P<cap>.+)\*$")


def render_markdown_with_local_images(md: str):
    matches = list(_MD_IMG_RE.finditer(md))
    if not matches:
        st.markdown(md, unsafe_allow_html=False)
        return

    parts: List[Tuple[str, str]] = []
    last = 0
    for m in matches:
        before = md[last:m.start()]
        if before:
            parts.append(("md", before))
        alt = (m.group("alt") or "").strip()
        src = (m.group("src") or "").strip()
        parts.append(("img", f"{alt}|||{src}"))
        last = m.end()
    tail = md[last:]
    if tail:
        parts.append(("md", tail))

    i = 0
    while i < len(parts):
        kind, payload = parts[i]

        if kind == "md":
            st.markdown(payload, unsafe_allow_html=False)
            i += 1
            continue

        alt, src = payload.split("|||", 1)

        caption = None
        if i + 1 < len(parts) and parts[i + 1][0] == "md":
            nxt = parts[i + 1][1].lstrip()
            if nxt.strip():
                first_line = nxt.splitlines()[0].strip()
                mcap = _CAPTION_LINE_RE.match(first_line)
                if mcap:
                    caption = mcap.group("cap").strip()
                    rest = "\n".join(nxt.splitlines()[1:])
                    parts[i + 1] = ("md", rest)

        if src.startswith("http://") or src.startswith("https://"):
            st.image(src, caption=caption or alt or None, use_container_width=True)
        else:
            # ✅ FIX 3 — try multiple path resolutions for local images
            candidates = [
                Path(src),
                Path(src.lstrip("./")),
                Path.cwd() / src,
                Path.cwd() / src.lstrip("./"),
            ]
            found = next((p for p in candidates if p.exists()), None)
            if found:
                st.image(str(found), caption=caption or alt or None, use_container_width=True)
            else:
                st.warning(f"Image not found: `{src}`")

        i += 1


# ── Session state init ────────────────────────────────────────────────────────

if "last_out" not in st.session_state:
    st.session_state["last_out"] = None

if "logs" not in st.session_state:
    st.session_state["logs"] = []

# ✅ FIX 2 — cache past blogs in session_state, only fetch once per session
if "past_blogs_cache" not in st.session_state:
    try:
        data = api_get("/api/blogs")
        st.session_state["past_blogs_cache"] = data.get("blogs", [])
    except Exception:
        st.session_state["past_blogs_cache"] = []

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.title("DeepDraft — Research-backed content generation")

with st.sidebar:
    st.header("Generate New Blog")
    topic = st.text_area("Topic", height=120)
    as_of = st.date_input("As-of date", value=date.today())
    run_btn = st.button("🚀 Generate Blog", type="primary")

    st.divider()
    st.subheader("Past Blogs")

    # ✅ FIX 2 — refresh button to explicitly reload past blogs list
    if st.button("🔄 Refresh list", use_container_width=True):
        try:
            data = api_get("/api/blogs")
            st.session_state["past_blogs_cache"] = data.get("blogs", [])
        except Exception as e:
            st.error(f"Failed to refresh: {e}")
        st.rerun()

    past_blogs = st.session_state["past_blogs_cache"]

    if not past_blogs:
        st.caption("No saved blogs found.")
    else:
        options = [f"{b['title']}  ·  {b['filename']}" for b in past_blogs[:50]]
        blog_by_label = {f"{b['title']}  ·  {b['filename']}": b for b in past_blogs[:50]}

        selected_label = st.radio(
            "Select a blog to load",
            options=options,
            index=0,
            label_visibility="collapsed",
        )
        selected_blog = blog_by_label.get(selected_label)

        if st.button("📂 Load selected blog", use_container_width=True):
            if selected_blog:
                try:
                    blog_content = api_get(f"/api/blogs/{selected_blog['filename']}")
                    # ✅ FIX 4 — store all fields so tabs don't show blank
                    st.session_state["last_out"] = {
                        "plan": None,
                        "evidence": [],
                        "image_specs": [],
                        "final": blog_content["content"],
                        "blog_title": selected_blog["title"],
                        "mode": "loaded from file",
                        "image_count": 0,
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load blog: {e}")

# ── Main tabs ─────────────────────────────────────────────────────────────────

tab_plan, tab_evidence, tab_preview, tab_images, tab_logs = st.tabs([
    "🧩 Plan", "🔎 Evidence", "📝 Markdown Preview", "🖼️ Images", "🧾 Logs"
])

# ── Generate ──────────────────────────────────────────────────────────────────

if run_btn:
    if not topic.strip():
        st.warning("Please enter a topic.")
        st.stop()

    st.session_state["logs"] = []

    status = st.status("Running Blog Writing Agent…", expanded=True)
    progress_area = st.empty()

    for event in stream_generate(topic.strip(), as_of.isoformat()):
        event_type = event.get("type")

        if event_type == "node":
            node_name = event.get("name", "")
            status.write(f"➡️ Node: `{node_name}`")
            st.session_state["logs"].append(f"[node] {node_name}")

        elif event_type == "summary":
            progress_area.json(event.get("data", {}))

        elif event_type == "done":
            # ✅ FIX 1 — store full plan + evidence from done event
            st.session_state["last_out"] = {
                "plan": event.get("plan"),
                "evidence": event.get("evidence", []),
                "image_specs": event.get("image_specs", []),
                "final": event.get("final_md", ""),
                "blog_title": event.get("blog_title", ""),
                "mode": event.get("mode", ""),
                "image_count": event.get("image_count", 0),
            }
            # ✅ FIX 2 — refresh past blogs cache after new generation
            try:
                data = api_get("/api/blogs")
                st.session_state["past_blogs_cache"] = data.get("blogs", [])
            except Exception:
                pass
            status.update(label="✅ Done", state="complete", expanded=False)
            st.session_state["logs"].append("[done] blog generated successfully")
            st.rerun()

        elif event_type == "error":
            status.update(label="❌ Error", state="error", expanded=True)
            status.write(f"Error: {event.get('content')}")
            st.session_state["logs"].append(f"[error] {event.get('content')}")

# ── Render output ─────────────────────────────────────────────────────────────

out = st.session_state.get("last_out")

if out:

    # ── Plan tab ──────────────────────────────────────────────────────────────
    with tab_plan:
        st.subheader("Plan")
        plan_obj = out.get("plan")
        if not plan_obj:
            st.info("No plan metadata available — this blog was loaded from file.")
        else:
            plan_dict = plan_obj if isinstance(plan_obj, dict) else plan_obj.model_dump()

            st.write("**Title:**", plan_dict.get("blog_title"))
            cols = st.columns(3)
            cols[0].write("**Audience:** " + str(plan_dict.get("audience", "")))
            cols[1].write("**Tone:** " + str(plan_dict.get("tone", "")))
            cols[2].write("**Blog kind:** " + str(plan_dict.get("blog_kind", "")))

            tasks = plan_dict.get("tasks", [])
            if tasks:
                df = pd.DataFrame([{
                    "id": t.get("id"),
                    "title": t.get("title"),
                    "target_words": t.get("target_words"),
                    "requires_research": t.get("requires_research"),
                    "requires_citations": t.get("requires_citations"),
                    "requires_code": t.get("requires_code"),
                    "tags": ", ".join(t.get("tags") or []),
                } for t in tasks]).sort_values("id")
                st.dataframe(df, use_container_width=True, hide_index=True)
                with st.expander("Task details"):
                    st.json(tasks)

    # ── Evidence tab ──────────────────────────────────────────────────────────
    with tab_evidence:
        st.subheader("Evidence")
        evidence = out.get("evidence") or []
        mode = out.get("mode", "")
        if not evidence:
            if "closed_book" in mode:
                st.info("No evidence — this blog was generated in closed_book mode (no web research needed).")
            else:
                st.info("No evidence available for this blog.")
        else:
            rows = []
            for e in evidence:
                if hasattr(e, "model_dump"):
                    e = e.model_dump()
                rows.append({
                    "title": e.get("title"),
                    "published_at": e.get("published_at"),
                    "source": e.get("source"),
                    "url": e.get("url"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Preview tab ───────────────────────────────────────────────────────────
    with tab_preview:
        st.subheader("Markdown Preview")
        final_md = out.get("final") or ""
        if not final_md:
            st.warning("No markdown found.")
        else:
            render_markdown_with_local_images(final_md)

            blog_title = out.get("blog_title") or extract_title(final_md, "blog")
            md_filename = f"{safe_slug(blog_title)}.md"

            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "⬇️ Download Markdown",
                    data=final_md.encode("utf-8"),
                    file_name=md_filename,
                    mime="text/markdown",
                )
            with col2:
                bundle = bundle_zip(final_md, md_filename)
                st.download_button(
                    "📦 Download Bundle (MD + images)",
                    data=bundle,
                    file_name=f"{safe_slug(blog_title)}_bundle.zip",
                    mime="application/zip",
                )

    # ── Images tab ────────────────────────────────────────────────────────────
    with tab_images:
        st.subheader("Images")
        specs = out.get("image_specs") or []
        images_dir = Path("artifacts/images")

        if not specs and not images_dir.exists():
            st.info("No images generated for this blog.")
        else:
            if specs:
                st.write("**Image plan:**")
                st.json(specs)

            if images_dir.exists():
                files = [p for p in images_dir.iterdir() if p.is_file()]
                if not files:
                    st.warning("images/ exists but is empty.")
                else:
                    for p in sorted(files):
                        st.image(str(p), caption=p.name, use_container_width=True)

                    buf = BytesIO()
                    with zipfile.ZipFile(buf, "w") as z:
                        for p in sorted(files):
                            z.write(p, arcname=p.name)
                    st.download_button(
                        "⬇️ Download Images (zip)",
                        data=buf.getvalue(),
                        file_name="images.zip",
                        mime="application/zip",
                    )

    # ── Logs tab ──────────────────────────────────────────────────────────────
    with tab_logs:
        st.subheader("Logs")
        st.text_area(
            "Event log",
            value="\n\n".join(st.session_state["logs"][-80:]),
            height=520,
        )

else:
    with tab_preview:
        st.info("Enter a topic and click **Generate Blog**.")