from __future__ import annotations

import logging
import os
from typing import Iterable, List, Sequence

import httpx
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def _get_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


FPT_RERANKER_API_KEY = os.getenv("FPT_RERANKER_API_KEY") or os.getenv("FPT_EMBEDDING_API_KEY")
FPT_RERANKER_MODEL = os.getenv("FPT_RERANKER_MODEL", "bge-reranker-v2-m3")
FPT_RERANKER_BASE_URL = os.getenv("FPT_RERANKER_BASE_URL", "https://mkp-api.fptcloud.com")
FPT_RERANKER_TIMEOUT = _get_float_env("FPT_RERANKER_TIMEOUT", 30.0)
FPT_RERANKER_MAX_DOCS = int(os.getenv("FPT_RERANKER_MAX_DOCS", "200"))
FPT_RERANKER_MAX_CHARS = int(os.getenv("FPT_RERANKER_MAX_CHARS", "120000"))


class FPTReranker:

    def __init__(
        self,
        model_name: str = FPT_RERANKER_MODEL,
        api_key: str | None = FPT_RERANKER_API_KEY,
        base_url: str = FPT_RERANKER_BASE_URL,
        timeout: float = FPT_RERANKER_TIMEOUT,
        max_documents: int = FPT_RERANKER_MAX_DOCS,
        top_n: int = 3,
        max_chars: int = FPT_RERANKER_MAX_CHARS,
    ):
        if not api_key:
            raise ValueError(
                "FPT reranker API key missing. "
                "Set FPT_RERANKER_API_KEY or reuse FPT_EMBEDDING_API_KEY."
            )
        self.model_name = model_name or FPT_RERANKER_MODEL
        self.timeout = timeout
        self.max_documents = max(1, max_documents)
        self.top_n = max(1, top_n)
        self.max_chars = max(0, max_chars)
        self._truncate_warned = False
        base = (base_url or FPT_RERANKER_BASE_URL).rstrip("/")
        if not base:
            raise ValueError("FPT reranker base URL is missing.")
        self._client = httpx.Client(
            base_url=base,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        self._endpoint = "/v1/rerank"

    def _extract_scores(self, payload: dict) -> List[tuple[int, float]]:
        data: Sequence[dict] | None = None
        if isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                data = payload["data"]
            elif isinstance(payload.get("results"), list):
                data = payload["results"]
        if not data:
            raise ValueError("Unexpected response from FPT reranker.")
        scores: List[tuple[int, float]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            idx = (
                item.get("index")
                or item.get("document_index")
                or item.get("doc_id")
                or item.get("id")
            )
            if idx is None:
                continue
            try:
                idx_int = int(idx)
            except (ValueError, TypeError):
                continue
            score = (
                item.get("relevance_score")
                or item.get("score")
                or item.get("relevance")
            )
            if score is None:
                continue
            try:
                score_float = float(score)
            except (ValueError, TypeError):
                continue
            scores.append((idx_int, score_float))
        return scores

    def _prepare_doc(self, text: str) -> str:
        value = (text or "").strip()
        if self.max_chars and len(value) > self.max_chars:
            if not self._truncate_warned:
                logger.warning(
                    "Reranker document exceeded %s characters. Truncating to comply with FPT limits.",
                    self.max_chars,
                )
                self._truncate_warned = True
            return value[: self.max_chars]
        return value

    def rerank(self, query: str, documents: Iterable[Document]) -> List[Document]:
        docs_list = list(documents)
        if not docs_list:
            return []
        limited_docs = docs_list[: self.max_documents]
        inputs = [self._prepare_doc(doc.page_content or "") for doc in limited_docs]
        payload = {
            "model": self.model_name,
            "query": query,
            "documents": inputs,
            "top_n": min(self.top_n, len(limited_docs)),
        }
        try:
            response = self._client.post(self._endpoint, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            snippet = ""
            try:
                snippet = exc.response.text[:500]
            except Exception:
                pass
            raise RuntimeError(
                f"FPT reranker API failed with {exc.response.status_code} {exc.response.reason_phrase}. "
                f"Snippet: {snippet}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"FPT reranker request failed: {exc}") from exc

        scores = self._extract_scores(response.json())
        if not scores:
            logger.warning("FPT reranker returned empty scores, skipping rerank.")
            return limited_docs[: self.top_n]
        ranked = sorted(scores, key=lambda x: x[1], reverse=True)
        top_docs: List[Document] = []
        for idx, _score in ranked[: self.top_n]:
            if 0 <= idx < len(limited_docs):
                top_docs.append(limited_docs[idx])
        return top_docs or limited_docs[: self.top_n]

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def __del__(self) -> None:
        self.close()


