from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

def _ensure_project_root() -> Path:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root

PROJECT_ROOT = _ensure_project_root()

if TYPE_CHECKING:
    from ai.LLMService import LLMService

load_dotenv()


def _parse_allowed_origins() -> list[str]:
    origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_llm_service() -> "LLMService":
    from ai.LLMService import LLMService as _LLMService

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise RuntimeError("Missing GROQ_API_KEY environment variable.")
    return _LLMService(
        groq_api_key=groq_api_key,
    )

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    tool_id: Optional[str] = None
    image_base64: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    role: str = "assistant"
    content: str


class ResetRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


class ResetResponse(BaseModel):
    session_id: str


app = FastAPI(title="UIT AI Chatbot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_allowed_origins() or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: "LLMService" = Depends(get_llm_service),
):
    try:
        result = await run_in_threadpool(service, payload.message, payload.session_id)
    except Exception as exc:
        print(f"Error processing chat request: {exc}")
        raise HTTPException(status_code=500, detail="Internal Server Error") from exc

    messages = result.get("messages") if isinstance(result, dict) else None
    if messages:
        latest = messages[-1]
        content = getattr(latest, "content", "") or ""
    else:
        content = ""

    return ChatResponse(session_id=payload.session_id, content=str(content))


@app.post("/chat/reset", response_model=ResetResponse)
async def reset_chat(
    payload: ResetRequest,
    service: "LLMService" = Depends(get_llm_service),
):
    try:
        await run_in_threadpool(service.reset_memory, payload.session_id)
    except Exception as exc:
        print(f"Error resetting chat session: {exc}")
        raise HTTPException(status_code=500, detail="Internal Server Error") from exc

    new_session_id = str(uuid4())
    return ResetResponse(session_id=new_session_id)


__all__ = ["app"]

