# GDGoC-UIT-Chatbot Monorepo

Generative AI chatbot for the UIT curriculum. The repository contains the Groq-powered LangGraph pipeline (`ai/`), the FastAPI transport layer (`backend/`), and a Vite + React + shadcn/tailwind client (`frontend/`).

## Repository layout

| Folder      | Purpose                                                                 |
|-------------|-------------------------------------------------------------------------|
| `ai/`       | Data loaders, semantic chunker, retrievers, Groq LangGraph pipeline.    |
| `backend/`  | FastAPI surface that exposes health checks and the `/chat` endpoint.    |
| `frontend/` | Vite React client with shadcn components and TailwindCSS styling.       |

## Requirements

- Python 3.11+ (install backend deps with `uv pip install -r requirements.txt`)
- Node.js 18+ with `npm`
- A Groq API key (`llama-3.3-70b-versatile` is used by default)
- A running Qdrant cluster (Cloud or self-hosted) with an API key
- An FPT AI Marketplace API key for the `Vietnamese_Embedding` model
- `fastembed` runtime dependency (already in `requirements.txt`) to generate sparse vectors for hybrid search
- (Optional) CUDA-capable GPU for accelerating embedding builds

## Backend API (FastAPI ↔ `ai`)

1. Install dependencies:
   ```bash
   uv pip install -r .\requirements.txt --index-strategy unsafe-best-match
   ```
2. Configure environment variables (e.g. `.env` at the repo root):
   ```env
   GROQ_API_KEY=your_key
   QDRANT_URL=https://<your-qdrant-endpoint>
   QDRANT_API_KEY=your_qdrant_api_key
   QDRANT_COLLECTION=uit_edu
   # QDRANT_PREFER_GRPC=true  # optional
   FPT_EMBEDDING_API_KEY=your_fpt_marketplace_key
   FPT_EMBEDDING_MODEL=Vietnamese_Embedding
   FPT_RERANKER_MODEL=bge-reranker-v2-m3
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
  "message": "CS311 có bao nhiêu tín chỉ?",
  "session_id": "uuid",
  "tool_id": null,
  "image_base64": null
}
```

The FastAPI route instantiates `ai.LLMService`, runs the LangGraph agent inside a worker thread, and returns the most recent assistant message.

## AI knowledge pipeline (`ai/`)

- Markdown sources live under `ai/dataset/`.
- `ai/Splitters.py` performs Markdown-aware + semantic chunking and annotates metadata (course headers, section paths, etc.) before a max-size pass (850 char chunks, 120 overlap).
- `ai/EmbeddingManager.py` calls the FPT AI Marketplace `Vietnamese_Embedding` API for dense vectors and wraps `fastembed.SparseTextEmbedding` (BM42) for sparse vectors. Long Markdown sections are automatically clipped to `FPT_EMBEDDING_MAX_CHARS` (default 120 000) before hitting the API so large tables do not trigger HTTP 400 errors.
- `ai/Reranker.py` sends the candidate documents to FPT’s `bge-reranker-v2-m3` API, replacing the on-device HuggingFace cross-encoder. Tweak `FPT_RERANKER_*` env vars to change model, key, timeout, or max docs per call.
- `ai/Vectors.py` uploads both dense (`dense`) and sparse (`sparse`) vectors into Qdrant, enabling first-class hybrid search inside the database. The collection schema is created automatically if it does not exist, UUID4 IDs are assigned per point, and upserts are chunked (`QDRANT_UPSERT_BATCH`) to avoid timeouts.
- `ai/FullChain.py` wires the hybrid retriever (Qdrant hybrid + local term-hit filter), calls the cloud reranker, and exposes the retrieval LangGraph tool consumed by `ai/LLMService`.

### Rebuilding the vector store

Whenever the dataset under `ai/dataset/` changes, rebuild the Qdrant collection:

```python
from dotenv import load_dotenv
from ai.FullChain import build_index

load_dotenv()
build_index()
```

The helper loads `.env`, runs the Markdown loader/splitter, and pushes both dense + sparse vectors to Qdrant. Make sure the following variables are available in your environment before running the script:

- `FPT_EMBEDDING_API_KEY`, `FPT_EMBEDDING_MODEL`, `FPT_EMBEDDING_BASE_URL` (if you override the default)
- `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`
- `QDRANT_VECTOR_NAME` / `QDRANT_SPARSE_VECTOR_NAME` if you do not want the defaults `dense` / `sparse`

`RetrieverService` automatically connects to the collection on startup, so a successful indexing step is all that is needed for the backend to serve queries with the new data.

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