# GDGoC-UIT-Chatbot Monorepo

Generative AI chatbot for the UIT curriculum. The repository contains the Groq-powered LangGraph pipeline (`ai/`), the FastAPI transport layer (`backend/`), and a Vite + React + shadcn/tailwind client (`frontend/`).

## Repository layout

| Folder      | Purpose                                                                 |
|-------------|-------------------------------------------------------------------------|
| `ai/`       | Data loaders, semantic chunker, retrievers, Groq LangGraph pipeline.    |
| `backend/`  | FastAPI surface that exposes health checks and the `/chat` endpoint.    |
| `frontend/` | Vite React client with shadcn components and TailwindCSS styling.       |

## Requirements

- Python 3.11+ with `pip` or [uv](https://github.com/astral-sh/uv)
- Node.js 18+ with `npm`
- A Groq API key (`llama-3.3-70b-versatile` is used by default)
- (Optional) CUDA-capable GPU for accelerating embedding builds

## Backend API (FastAPI ↔ `ai`)

1. Install dependencies:
   ```bash
   uv pip install -r .\requirements.txt --index-strategy unsafe-best-match
   ```
2. Configure environment variables (e.g. `.env` at the repo root):
   ```env
   GROQ_API_KEY=your_key
   ```
3. Run the API:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```

### HTTP surface

| Method | Path     | Description                               |
|--------|----------|-------------------------------------------|
| GET    | `/health`| Liveness probe (`{"status": "ok"}`).      |
| POST   | `/chat`  | Accepts a chat turn and streams to Groq.  |

`POST /chat` expects:

```json
{
  "message": "Cần bao nhiêu tín chỉ tốt nghiệp?",
  "session_id": "uuid",
  "tool_id": null,
  "image_base64": null
}
```

The FastAPI route instantiates `ai.LLMService`, runs the LangGraph agent inside a worker thread, and returns the most recent assistant message.

## AI knowledge pipeline (`ai/`)

- Markdown sources live under `ai/dataset/`.
- Semantic chunking is handled by `ai/Splitters.py` (Markdown headers + SemanticChunker).
- `ai/Vectors.py` maintains a local Chroma index in `ai/.index/chroma`.
- `ai/FullChain.py` wires the retriever stack (BM25 + dense + term hits), reranks with `HuggingFaceCrossEncoder`, and exposes a LangGraph tool for Groq's `ChatGroq`.

### Rebuilding the vector store

Execute the following from the repo root whenever the dataset changes:

```python
from ai.EmbeddingManager import get_encoder
from ai.Loaders import load_markdown
from ai.Splitters import split_markdown
from ai.Vectors import build_index

docs = load_markdown()
encoder = get_encoder()
chunks = split_markdown(docs, encoder, show_progress=True)
build_index(chunks, encoder)
```

The default settings persist embeddings to `ai/.index/chroma`, which `RetrieverService` automatically loads when the backend starts.

## Frontend (React + Vite + shadcn + TailwindCSS 3)

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Create `frontend/.env` if you need a non-default API URL:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   ```
3. Available scripts:
   ```bash
   npm run dev      # start Vite dev server on :5173
   npm run build    # type-check + production build
   npm run preview  # preview the production build
   npm run lint     # TypeScript-only lint pass
   ```

The UI lives in `frontend/src/components/ui`, reusing shadcn primitives (see `components.json`). `App.tsx` orchestrates the chat experience, talking to `frontend/src/lib/api.ts`, which forwards payloads to `POST /chat`.

## Connecting the layers

- The frontend sends JSON payloads via `sendPrompt` → `POST /chat`.
- FastAPI hands control to `ai.LLMService`, which uses Groq + LangGraph tools over the UIT curriculum embeddings.
- Update `VITE_API_BASE_URL` and `CORS_ALLOW_ORIGINS` together when deploying to different hosts to avoid browser preflight issues.