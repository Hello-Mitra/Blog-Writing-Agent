from __future__ import annotations

import sys
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.logger import logging
from src.exception import MyException
from src.schemas.models import State, GlobalImagePlan
from src.prompts.templates import DECIDE_IMAGES_SYSTEM
from src.tools.slug import safe_slug
from src.image.image_generator import generate_image_bytes
from entity.config_entity import OutputConfig


def build_merge_content_node():
    """
    Returns the merge_content node function.

    The merge_content node is the first step of the reducer subgraph.
    It runs after all worker nodes have completed. At this point
    state['sections'] contains all (task_id, section_md) tuples.

    This node sorts sections by task_id to restore the correct order
    (parallel workers may complete out of order), joins them into a
    single markdown body, and prepends the H1 blog title.

    Returns:
        merge_content function compatible with StateGraph.add_node.
    """
    def merge_content(state: State) -> dict:
        try:
            plan = state["plan"]
            if plan is None:
                raise ValueError("merge_content called without a plan in state.")

            ordered_sections = [
                md for _, md in sorted(state["sections"], key=lambda x: x[0])
            ]
            body = "\n\n".join(ordered_sections).strip()
            merged_md = f"# {plan.blog_title}\n\n{body}\n"

            logging.info(f"merge_content — merged {len(ordered_sections)} sections into {len(merged_md)} chars")
            return {"merged_md": merged_md}

        except Exception as e:
            raise MyException(e, sys)

    return merge_content


def build_decide_images_node(llm: ChatOpenAI):
    """
    Factory that returns the decide_images node function.

    The decide_images node is the second step of the reducer subgraph.
    It asks the LLM to decide whether any images or diagrams would
    materially improve the blog. If yes, it inserts [[IMAGE_N]]
    placeholders into the markdown and generates ImageSpec objects
    describing what to generate.

    If no images are needed, md_with_placeholders equals merged_md
    and image_specs is an empty list.

    Args:
        llm: The ChatOpenAI instance used for image planning.

    Returns:
        decide_images function compatible with StateGraph.add_node.
    """
    planner = llm.with_structured_output(GlobalImagePlan)

    def decide_images(state: State) -> dict:
        try:
            plan = state["plan"]
            if plan is None:
                raise ValueError("decide_images called without a plan in state.")

            merged_md = state["merged_md"]
            logging.info(f"decide_images — evaluating image needs for '{plan.blog_title}'")

            image_plan = planner.invoke([
                SystemMessage(content=DECIDE_IMAGES_SYSTEM),
                HumanMessage(content=(
                    f"Blog kind: {plan.blog_kind}\n"
                    f"Topic: {state['topic']}\n\n"
                    "Insert placeholders + propose image prompts.\n\n"
                    f"{merged_md}"
                )),
            ])

            logging.info(f"decide_images — {len(image_plan.images)} images planned")
            return {
                "md_with_placeholders": image_plan.md_with_placeholders,
                "image_specs": [img.model_dump() for img in image_plan.images],
            }

        except Exception as e:
            raise MyException(e, sys)

    return decide_images


def build_generate_and_place_images_node(config: OutputConfig = None):
    """
    Factory that returns the generate_and_place_images node function.

    The generate_and_place_images node is the final step of the reducer
    subgraph. It iterates over image_specs, generates each image using
    Gemini, saves it to the configured images_dir, and replaces the
    [[IMAGE_N]] placeholder in the markdown with a proper img tag.

    If image generation fails for any spec, a graceful fallback block
    is inserted instead of the placeholder so the blog remains readable.

    The final markdown is saved to output_dir as a .md file and also
    returned in state['final'].

    Args:
        config: OutputConfig with output_dir and images_dir paths.

    Returns:
        generate_and_place_images function compatible with StateGraph.
    """
    if config is None:
        config = OutputConfig()

    def generate_and_place_images(state: State) -> dict:
        try:
            import re

            plan = state["plan"]
            if plan is None:
                raise ValueError("generate_and_place_images called without a plan.")

            md = state.get("md_with_placeholders") or state["merged_md"]
            image_specs = state.get("image_specs") or []

            images_dir = Path(config.images_dir)
            output_dir = Path(config.output_dir)
            images_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)

            if not image_specs:
                logging.info("No images requested — saving markdown directly")
                filename = f"{safe_slug(plan.blog_title)}.md"
                (output_dir / filename).write_text(md, encoding="utf-8")
                return {"final": md}

            # ── Log placeholder state for debugging ───────────────────────
            placeholders_in_md = re.findall(r'\[\[IMAGE_\d+\]\]', md, flags=re.IGNORECASE)
            placeholders_in_specs = [s["placeholder"] for s in image_specs]
            logging.info(f"Placeholders in markdown: {placeholders_in_md}")
            logging.info(f"Placeholders in specs: {placeholders_in_specs}")

            missing = [p for p in placeholders_in_specs if p not in placeholders_in_md]
            if missing:
                logging.warning(f"Placeholders missing from markdown (will append): {missing}")

            # ── Process each image spec ───────────────────────────────────
            for spec in image_specs:
                placeholder = spec["placeholder"]
                bare_filename = Path(spec["filename"]).name
                out_path = images_dir / bare_filename

                # Generate image if it doesn't already exist
                if not out_path.exists():
                    try:
                        img_bytes = generate_image_bytes(
                            spec["prompt"],
                            size=spec.get("size", "1024x1024"),
                            quality="standard",
                        )
                        out_path.write_bytes(img_bytes)
                        logging.info(f"Image saved: {out_path}")
                    except Exception as e:
                        logging.warning(f"Image generation failed for {placeholder}: {e}")
                        fallback = (
                            f"> **[IMAGE GENERATION FAILED]** {spec.get('caption', '')}\n>\n"
                            f"> **Alt:** {spec.get('alt', '')}\n>\n"
                            f"> **Prompt:** {spec.get('prompt', '')}\n>\n"
                            f"> **Error:** {e}\n"
                        )
                        # Replace placeholder if it exists, else append
                        if re.search(re.escape(placeholder), md, flags=re.IGNORECASE):
                            md = re.sub(re.escape(placeholder), fallback, md, flags=re.IGNORECASE)
                        else:
                            md = md.rstrip("\n") + f"\n\n{fallback}\n"
                        continue

                img_md = f"![{spec['alt']}]({config.images_dir}/{bare_filename})\n*{spec['caption']}*"

                # ✅ Place inline if placeholder exists, else append at end
                if re.search(re.escape(placeholder), md, flags=re.IGNORECASE):
                    md = re.sub(re.escape(placeholder), img_md, md, flags=re.IGNORECASE)
                    logging.info(f"Placed {placeholder} inline in markdown")
                else:
                    logging.warning(f"{placeholder} not in markdown — appending at end")
                    md = md.rstrip("\n") + f"\n\n{img_md}\n"

            # ── Save final markdown ───────────────────────────────────────
            filename = f"{safe_slug(plan.blog_title)}.md"
            output_path = output_dir / filename
            output_path.write_text(md, encoding="utf-8")
            logging.info(f"Blog saved to {output_path}")

            return {"final": md}

        except Exception as e:
            raise MyException(e, sys)

    return generate_and_place_images
