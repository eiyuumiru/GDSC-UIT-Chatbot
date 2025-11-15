# GDGoC-UIT-Chatbot Monorepo

This repository now follows a clean multi-folder structure:

| Folder    | Purpose                                                                                   |
|-----------|-------------------------------------------------------------------------------------------|
| `ai/`     | LangChain / RAG pipeline, retrievers, loaders, vector stores, etc. (former `backend/`).   |
| `backend/`| FastAPI bridge that exposes the AI pipeline to the outside world.                         |
| `frontend/`| React + Vite + TypeScript + Tailwind + shadcn/ui client (replacing the old Streamlit UI).|

## Backend (FastAPI ↔ ai)

1. Install dependencies:
   ```bash
   uv pip install -r requirements.txt   # or: pip install -r requirements.txt
   ```
2. Set the required environment variables (e.g. in a `.env` file at repo root):
   ```env
   GROQ_API_KEY=...
   GROQ_MODEL_NAME=llama-3.3-70b-versatile
   GROQ_TEMPERATURE=0.5
   CORS_ALLOW_ORIGINS=http://localhost:5173
   ```
3. Run the API:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
   The FastAPI app imports `ai.LLMService` and other helpers from the `ai` package, so both folders stay isolated but connected.

## Frontend (React + shadcn + Tailwind 4)

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Configure the API endpoint in `frontend/.env` (defaults to `http://localhost:8000`):
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   ```
3. Start the dev server:
   ```bash
   npm run dev
   ```

### shadcn project structure

The shadcn CLI is already initialized via `components.json`, using the aliases:

- `@/components/ui` → default directory for reusable UI primitives (e.g. `PromptBox` lives in `frontend/src/components/ui/chatgpt-prompt-input.tsx`).
- `@/components` → composite components.
- `@/lib/utils` → utility helpers (contains the `cn` helper).

To add more shadcn components:
```bash
npx shadcn@latest add button
```
They will automatically be generated under `src/components/ui`, so there is no need to manually rearrange files.

### Tailwind & styling

- Tailwind 4 is enabled through `src/index.css`, which already imports:
  ```css
  @import "tailwindcss";
  @import "tw-animate-css";
  :root { --radius: 0.65rem; }
  ```
- Custom animation utilities live in `src/styles/tw-animate-css.css`.
- Global design tokens and shadcn variables are also defined inside `src/index.css`.

### Prompt input component

The high-fidelity prompt component provided in the task is integrated as `PromptBox` in `frontend/src/components/ui/chatgpt-prompt-input.tsx`, and a live showcase is available via `PromptBoxDemo` for Storybook-style testing. The component relies on:

- `@radix-ui/react-tooltip`, `@radix-ui/react-popover`, `@radix-ui/react-dialog`
- `lucide-react` icons (per requirement to use lucide instead of raw SVGs)
- Hidden inputs (`selectedTool`, `imageData`) so FastAPI receives the correct metadata

## Connecting the layers

- Frontend submits chat payloads to `POST /chat` exposed by `backend/main.py`.
- The FastAPI route calls into `ai.LLMService`, which runs the Groq-powered LangChain pipeline.
- Update `VITE_API_BASE_URL` if the backend runs on a different host/port, and adjust `CORS_ALLOW_ORIGINS` accordingly so browsers can reach the API.

## Removing Streamlit

Streamlit has been fully removed from the repository. All UI work now happens inside the `frontend` React app, keeping the Python layers focused on inference. If any residual Streamlit files reappear, they can be safely deleted because they are no longer part of the architecture.


