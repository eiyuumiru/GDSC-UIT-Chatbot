# AskUIT

AskUIT is a UIT-focused chatbot powered by Groq + LangGraph. It retrieves knowledge from Qdrant (hybrid dense/sparse) and can search UIT domains via Tavily. The monorepo contains the AI pipeline (`ai/`), a FastAPI backend (`backend/`), and a Vite/React client (`frontend/`).

## Architecture
- Groq LLM via LiteLLM router (guardrail → planner → tools → generator/advisor).
- Tool `retrieve`: Qdrant hybrid (FPT dense embedding + fastembed BM25 sparse) + FPT reranker.
- Tool `tavily_search`: UIT domain-filtered web search for fresh news/policies.
- FastAPI transport: `/health`, `/chat`, `/chat/reset`.
- UI: Vite + React + shadcn/tailwind with theme switcher, copy/retry feedback, session restart.

## Repository structure
| Folder      | Description                                                           |
|-------------|------------------------------------------------------------------------|
| `ai/`       | LLMService, prompts, tools (`retrieve`, Tavily), index build scripts. |
| `backend/`  | FastAPI app, request/response schemas, CORS.                          |
| `frontend/` | Vite React UI (shadcn), chat hooks, API client.                       |

## Prerequisites
- Python 3.11+
- Node.js 18+ and `npm`
- Qdrant cluster (Cloud/self-hosted) with API key
- API keys: Groq, FPT embedding/reranker, Tavily

## Environment variables (root `.env`)
```
GROQ_API_KEY=...
QDRANT_URL=https://your-qdrant
QDRANT_API_KEY=...
CORS_ALLOW_ORIGINS=http://localhost:5173

# FPT Cloud (for both embed & rerank; rerank can reuse FPT_EMBEDDING_API_KEY)
FPT_EMBEDDING_API_KEY=...
FPT_RERANKER_API_KEY=...    # optional

# Tavily web search
TAVILY_API_KEY=...
```
Collection/vector names live in `ai/config/Qdrant.py` (defaults: collection `uit_edu_v2`, vectors `dense` / `sparse`).

## Run backend (FastAPI)
```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### API surface
- `GET /health` → `{"status": "ok"}`
- `POST /chat`  
  Body: `{ "message": "...", "session_id": "uuid?", "tool_id": null, "image_base64": null }`  
  Returns: `{ "session_id": "...", "role": "assistant", "content": "..." }`
- `POST /chat/reset`  
  Body: `{ "session_id": "..." }` → new `session_id`

### Processing flow
`LLMService` runs guardrail (intent), planner (decide parallel tools), tool node (retrieve + tavily), then generator/advisor to craft the final reply.

## RAG pipeline (`ai/`)
- Dense embedding: FPT `openai/Vietnamese_Embedding` via LiteLLM (`FPT_EMBEDDING_API_KEY`).
- Sparse embedding: fastembed BM25 (`Qdrant/bm25`).
- Rerank: FPT `bge-reranker-v2-m3` (`FPT_RERANKER_API_KEY` or embedding key).
- Qdrant hybrid search + rerank top-N, returning chunks to the LLM.

### Rebuild the Qdrant index
1) Place JSON data under `ai/dataset/CS311` (can fetch from public bucket `cs311_uswest` via `ai/GoogleCloud/getBucket.py`).  
2) Set Qdrant + FPT env vars as above.  
3) Run:
```bash
python ai/QdrantService/buildIndex.py
```
The script (re)upserts all JSON into Qdrant with dense + sparse vectors. Note: the cleaning helper (`cleanJSON.py`) uses `deep_translator` if you need prefix translation.

## Frontend (Vite + React + shadcn)
```bash
cd frontend
npm install
```
Optional API override:
```
VITE_API_BASE_URL=http://localhost:8000
```
Scripts:
```
npm run dev      # Vite dev server (5173)
npm run build    # type-check + production build
npm run preview  # preview build
npm run lint     # tsc --noEmit
```
Main UI in `frontend/src/App.tsx`, API client in `frontend/src/lib/api.ts`.

## Deploy notes
- Keep `VITE_API_BASE_URL` and `CORS_ALLOW_ORIGINS` in sync when changing host/port.
- `buildIndex.py` will overwrite the Qdrant collection; use with care in production.
- Without a Tavily key, web search tool fails and planner falls back to retrieve-only.