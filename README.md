# DeepDraft — AI-Powered Blog Writing Agent

> A production-grade agentic blog writing system that researches, plans, and writes complete technical blog posts with AI-generated images. Built with LangGraph's fan-out/fan-in architecture, FastAPI, and Streamlit.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)
![LangGraph](https://img.shields.io/badge/LangGraph-latest-green?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?style=flat-square&logo=fastapi)
![Streamlit](https://img.shields.io/badge/Streamlit-latest-FF4B4B?style=flat-square&logo=streamlit)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat-square&logo=docker)
![AWS](https://img.shields.io/badge/AWS-EC2%20%2B%20ECR-FF9900?style=flat-square&logo=amazonaws)

---

## Features

- **Intelligent Routing** — Automatically decides whether web research is needed before planning. Topics are classified as `closed_book` (evergreen), `hybrid` (needs recent examples), or `open_book` (news/weekly roundup).
- **Web Research** — Integrates Tavily search to gather evidence before writing. Filters results by recency and deduplicates by URL.
- **AI Blog Planning** — Orchestrator node generates a structured plan with 5–9 sections, each with goal, bullets, target word count, and section type.
- **Parallel Section Writing** — Uses LangGraph's Send API to dispatch all section writers in parallel. Each worker receives its task, the full plan, and grounded evidence.
- **AI Image Generation** — DALL-E 3 generates up to 3 technical diagrams per blog. Images are placed inline via placeholder substitution with graceful fallback on failure.
- **Sidecar Persistence** — Plan, evidence, and image specs are saved as a `.json` sidecar alongside each `.md` file so metadata survives browser refreshes.
- **Past Blog Library** — Load, preview, and download any previously generated blog from the sidebar.
- **SSE Streaming** — Live progress display showing each graph node as it executes.
- **LangSmith Observability** — Full tracing of every LangGraph run.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Frontend                       │
│    (topic input, live progress, plan/evidence/preview tabs)  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────────┐
│                      FastAPI Backend                         │
│         /api/generate/stream    /api/blogs    /health        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   LangGraph Pipeline                         │
│                                                              │
│  START → router → [research] → orchestrator                  │
│                                     │                        │
│                              fanout (Send API)               │
│                          ┌──────┬───┴───┬──────┐            │
│                       worker worker worker worker            │
│                          └──────┴───┬───┴──────┘            │
│                                     │                        │
│                              reducer subgraph                │
│                    merge_content → decide_images             │
│                         → generate_and_place_images          │
│                                     │                        │
│                                    END                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            │                             │
   ┌────────▼────────┐          ┌────────▼────────┐
   │   Tavily API    │          │  DALL-E 3 API   │
   │ (web research)  │          │ (image gen)     │
   └─────────────────┘          └─────────────────┘
```

---

## How It Works

```
1. User enters a topic and as-of date
        ↓
2. Router classifies the topic
   closed_book → skip research, go straight to planning
   hybrid      → research recent examples, then plan
   open_book   → research last 7 days of news, then plan
        ↓
3. [Optional] Research node
   → runs Tavily searches for all queries
   → LLM synthesizes results into EvidenceItems
   → deduplicates by URL, filters by recency
        ↓
4. Orchestrator generates a Plan
   → blog_title, audience, tone, blog_kind
   → 5-9 Task objects (one per section)
        ↓
5. Fanout dispatches all workers in parallel
   → each worker writes one Markdown section
   → workers run concurrently via LangGraph Send API
   → sections appended to state via operator.add reducer
        ↓
6. Reducer subgraph assembles the blog
   merge_content  → sorts sections by task ID, joins into full Markdown
   decide_images  → LLM decides if images are needed, inserts [[IMAGE_N]] placeholders
   generate_and_place_images → DALL-E 3 generates images, replaces placeholders
        ↓
7. Final Markdown + images saved to artifacts/blogs/
   Sidecar JSON saved with plan + evidence metadata
```

---

## Project Structure

```
DeepDraft/
│
├── backend/                        # FastAPI application
│   ├── main.py                     # App entry with lifespan startup
│   └── routes/
│       └── blog.py                 # /api/generate, /api/generate/stream, /api/blogs
│
├── frontend/                       # Streamlit UI
│   └── app.py                      # Live progress, tabs, past blog loader
│
├── pipeline/                       # Orchestration layer
│   └── blog_pipeline.py            # Builds main graph + reducer subgraph
│
├── src/
│   ├── graph/
│   │   └── nodes/
│   │       ├── router.py           # Classifies topic → mode + research decision
│   │       ├── research.py         # Tavily search + LLM synthesis
│   │       ├── orchestrator.py     # Generates Plan with Tasks
│   │       ├── worker.py           # Writes one section + fanout Send API
│   │       └── reducer.py          # merge_content + decide_images + generate_and_place_images
│   ├── schemas/
│   │   ├── models.py               # All Pydantic models + LangGraph State
│   │   └── requests.py             # FastAPI request/response schemas
│   ├── prompts/
│   │   └── templates.py            # All LLM system prompts
│   ├── research/
│   │   └── tavily_search.py        # Tavily wrapper with graceful fallback
│   ├── image/
│   │   └── image_generator.py      # DALL-E 3 image generation
│   ├── tools/
│   │   └── slug.py                 # safe_slug utility (shared)
│   ├── logger/                     # Rotating file + console logger
│   └── exception/                  # Custom exception with traceback
│
├── config/
│   └── settings.py                 # Pydantic settings — all config in one place
│
├── entity/
│   ├── config_entity.py            # LLMConfig, ResearchConfig, OutputConfig
│   └── artifact_entity.py          # BlogArtifact
│
├── artifacts/                      # Generated at runtime (gitignored)
│   ├── blogs/                      # Generated .md and .json sidecar files
│   └── images/                     # AI-generated images
│
├── tests/
│   ├── conftest.py                 # Shared fixtures
│   ├── test_schemas.py             # Pydantic model validation tests
│   ├── test_tools.py               # safe_slug + tavily_search unit tests
│   └── test_api.py                 # FastAPI endpoint tests
│
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── .github/workflows/cicd.yml      # CI/CD → AWS ECR → EC2
├── requirements.backend.txt
├── requirements.frontend.txt
└── .env.example
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM (writing) | GPT-4.1-mini (OpenAI) |
| Image Generation | DALL-E 3 (OpenAI) |
| Orchestration | LangGraph (fan-out/fan-in with Send API) |
| Web Research | Tavily Search API |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Observability | LangSmith |
| Containerization | Docker + Docker Compose |
| Registry | AWS ECR |
| Deployment | AWS EC2 |
| CI/CD | GitHub Actions |

---

## Getting Started

### Prerequisites

- Python 3.11+
- OpenAI API key (required — for LLM writing + DALL-E 3 images)
- Tavily API key (optional — enables web research for hybrid/open_book topics)
- LangSmith API key (optional — for observability)

### Local Setup

**1. Clone the repository:**
```bash
git clone https://github.com/Hello-Mitra/DeepDraft.git
cd DeepDraft
```

**2. Create virtual environment:**
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac/Linux
```

**3. Install dependencies:**
```bash
pip install -r requirements.backend.txt
pip install -r requirements.frontend.txt
```

**4. Create `.env` file:**
```bash
cp .env.example .env
# Fill in your API keys
```

**5. Run the backend:**
```bash
uvicorn backend.main:app --port 8000 --reload
```

**6. Run the frontend (new terminal):**
```bash
streamlit run frontend/app.py
```

**7. Open in browser:**
```
http://localhost:8501
```

### Docker Setup

```bash
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# Required
OPENAI_API_KEY=your_openai_api_key

# Optional — enables web research for hybrid and open_book topics
TAVILY_API_KEY=your_tavily_api_key

# Optional — LangSmith observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=DeepDraft

# Output directories (defaults shown, override if needed)
# OUTPUT_DIR=artifacts/blogs
# IMAGES_DIR=artifacts/images
```

---

## Routing Modes

DeepDraft automatically selects the appropriate research mode before writing:

| Mode | When Used | Research | Recency Window |
|---|---|---|---|
| `closed_book` | Evergreen concepts (e.g. "What is attention?") | None | — |
| `hybrid` | Needs recent examples (e.g. "Best RAG frameworks 2026") | Yes | Last 45 days |
| `open_book` | News/volatile topics (e.g. "AI news this week") | Yes | Last 7 days |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/generate` | Generate blog synchronously (blocks until complete) |
| `POST` | `/api/generate/stream` | Generate blog with SSE live progress streaming |
| `GET` | `/api/blogs` | List all generated blogs sorted newest-first |
| `GET` | `/api/blogs/{filename}` | Get markdown content + metadata of a specific blog |
| `GET` | `/health` | Health check |

Full interactive API docs at `http://localhost:8000/docs`

### Example Request

```json
POST /api/generate/stream
{
    "topic": "Building production-grade RAG pipelines in 2026",
    "as_of": "2026-04-09"
}
```

### SSE Event Types

```
node    → {"type": "node",    "name": "orchestrator"}
summary → {"type": "summary", "data": {"mode": "hybrid", "tasks": 7, ...}}
done    → {"type": "done",    "final_md": "...", "plan": {...}, "evidence": [...]}
error   → {"type": "error",   "content": "..."}
```

---

## LangGraph Architecture

```
Fan-out/fan-in pattern using LangGraph Send API:

orchestrator
    │
    └── fanout() → [Send("worker", task_1), Send("worker", task_2), ...]
                          │               │
                       worker_1        worker_2  ... (parallel)
                          │               │
                          └───────┬───────┘
                                  │
                             reducer subgraph
                          merge_content (sort + join)
                                  │
                          decide_images (LLM plans images)
                                  │
                    generate_and_place_images (DALL-E 3)
```

The `sections` field in State uses `Annotated[List[tuple], operator.add]` as the reducer — allowing all parallel workers to append their `(task_id, section_md)` tuples concurrently without overwriting each other.

---

## CI/CD Pipeline

```
git push origin main
        │
        ▼
Continuous-Integration (GitHub hosted runner)
        │
        ├── Lint with Ruff
        ├── Run pytest test suite
        ├── Build backend Docker image
        ├── Push to AWS ECR
        ├── Build frontend Docker image
        └── Push to AWS ECR
        │
        ▼
Continuous-Deployment (EC2 self-hosted runner)
        │
        ├── Fix workspace permissions
        ├── Pull latest images from ECR
        ├── docker-compose down
        └── docker-compose up -d
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

**Arijit Mitra**

[![GitHub](https://img.shields.io/badge/GitHub-Hello--Mitra-181717?style=flat-square&logo=github)](https://github.com/Hello-Mitra)