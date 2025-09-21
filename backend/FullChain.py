from __future__ import annotations
from typing import Dict, Any, List, Optional
import re
import time
import logging
from .Loaders import load_markdown
from .Splitters import split_markdown
from .EmbeddingManager import get_encoder
from .Vectors import build_index as build_vec, load_index as load_vec
from .Retriever import docs_from_chroma, make_hybrid_retriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_core.tools import tool, BaseTool
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

logger = logging.getLogger(__name__)

class RetrieverService:
    def __init__(self, model_name = "jinaai/jina-reranker-v2-base-multilingual", top_n: int = 6, weights: list[float] = [0.3, 0.6, 0.1]):
        self._ENC = self.__init_Encoder()
        self._DB = self.__init_DB()
        self._CHUNKS_FOR_BM25 = self.__init_ChunksForBM25()
        self._RERANKER: CrossEncoderReranker = self.__init_Reranker(model_name=model_name, top_n=top_n)
        self.hybrid_retriever = self.__init_HybridRetriever(weights=weights, k=top_n)
        self.top_n = top_n

    def __init_DB(self):
        try:
            return load_vec(encoder=self._ENC)
        except Exception as e:
            raise RuntimeError(f"Failed to load vector DB: {e}")

    def __init_Encoder(self):
        try:
            return get_encoder(batch_size=64)
        except Exception as e:
            raise RuntimeError(f"Failed to load encoder: {e}")

    def __init_ChunksForBM25(self):
        try:
            return docs_from_chroma(self._DB)
        except Exception as e:
            raise RuntimeError(f"Failed to load BM25 chunks: {e}")

    def __init_Reranker(self, model_name: str = "jinaai/jina-reranker-v2-base-multilingual", top_n: int = 6) -> CrossEncoderReranker:
        try:
            device = "cpu"
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
            except Exception:
                device = "cpu"
            logger.info("Initializing CrossEncoderReranker model=%s device=%s top_n=%s", model_name, device, top_n)
            model = HuggingFaceCrossEncoder(model_name=model_name, model_kwargs={"trust_remote_code": True, "device": device})
            return CrossEncoderReranker(model=model, top_n=top_n)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize reranker: {e}")
    
    def __init_HybridRetriever(self, weights: list[float] = [0.3, 0.6, 0.1], k: int = 6):
        try:
            return make_hybrid_retriever(self._CHUNKS_FOR_BM25, self._DB, k=k, weights=weights)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize hybrid retriever: {e}")

    def _retrieve_impl(self, query: str) -> tuple[str, List[Dict[str, Any]]]:
        t0 = time.perf_counter()
        logger.info("[retrieve] start query='%s' top_n=%s", query, self.top_n)
        k_init = max(60, self.top_n * 6)
        try:
            candidate_docs = self.hybrid_retriever.invoke(query)
        except Exception as e:
            logger.exception("[retrieve] hybrid retriever failed: %s", e)
            candidate_docs = []
        if not candidate_docs:
            try:
                candidate_docs = self._DB.as_retriever(search_kwargs={"k": k_init}).invoke(query)
            except Exception as e:
                logger.exception("[retrieve] vector store fallback failed: %s", e)
                candidate_docs = []

        t1 = time.perf_counter()
        try:
            ranked_docs = self._RERANKER.compress_documents(documents=candidate_docs, query=query)
            ranked_docs = ranked_docs[:self.top_n] if ranked_docs else candidate_docs[:self.top_n]
        except Exception as e:
            logger.exception("[retrieve] reranker failed, using top-k candidates: %s", e)
            ranked_docs = candidate_docs[:self.top_n]
        t2 = time.perf_counter()
        logger.info("[retrieve] done candidates=%s ranked=%s retrieve=%.3fs rerank=%.3fs", len(candidate_docs), len(ranked_docs), t1 - t0, t2 - t1)

        # # Debug logging
        # for idx, doc in enumerate(ranked_docs, start=1):
        #     chunk_text = (doc.page_content or "").strip().replace("\n", " ")
        #     if len(chunk_text) > 300:
        #         chunk_text = chunk_text[:300].rstrip() + "..."
        #     source = doc.metadata.get("source", "")
        #     print(f"[retrieve] #{idx} source={source} chunk={chunk_text}", flush=True)

        results: List[Dict[str, Any]] = [
            {"source": doc.metadata.get("source", ""), "content": doc.page_content}
            for doc in ranked_docs
        ]

        return query, results

def make_retrieve_tool(svc: RetrieverService) -> BaseTool:
    @tool(response_format="content_and_artifact")
    def _retrieve(query: str) -> tuple[str, List[Dict[str, Any]]]:
        """Retrieve information about UIT's academic curriculum (majors, courses, credits, and regulations) from the internal vector database."""
        return svc._retrieve_impl(query)
    return _retrieve


# def build_index(
#         data_dir: str = "backend/dataset",
#         percentile: int = 92,
#         enforce_max: int = 850,
#         overlap: int = 120,
#         batch_size: int = 64,
#         min_chunk_chars: int = 320,
#         soft_merge_chars: int = 160,
#         prefix_headers: bool = True,
#         clear_existing: bool = True,
#     ) -> Dict[str, Any]:
#         print("Phase 1/3: load docs ...", flush=True)
#         docs = load_markdown(data_dir)
#         print(f"Docs: {len(docs)}", flush=True)
#         print("Phase 2/3: semantic split ...", flush=True)
#         enc = get_encoder(batch_size=batch_size)
#         chunks = split_markdown(
#             docs,
#             encoder=enc,
#             percentile=percentile,
#             enforce_max=enforce_max,
#             overlap=overlap,
#             show_progress=True,
#             min_chunk_chars=min_chunk_chars,
#             soft_merge_chars=soft_merge_chars,
#             prefix_headers=prefix_headers,
#         )
#         print(f"Chunks: {len(chunks)}", flush=True)
#         print("Phase 3/3: build index ...", flush=True)
#         db = build_vec(chunks, enc, batch_size=batch_size, show_progress=True, clear_existing=clear_existing)
#         self._resolve_caches(db=db, enc=enc)
#         count = getattr(db._collection, "count")() if hasattr(db, "_collection") else None
#         return {"docs": len(docs), "chunks": len(chunks), "count": count}

class ContextFormatter:
    def __init__(self, max_chars: int = 8000, max_items: int = 6):
        self.max_chars = max_chars
        self.max_items = max_items

    def _normalize_text(self, piece: str) -> str:
        raw = (piece or "").strip()
        if not raw:
            return ""
        if "\n" in raw:
            lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines() if line.strip()]
            if lines and all(((":" in line) and line.index(":") <= 24) for line in lines):
                return "\n".join(f"- {line}" for line in lines)
            text = " ".join(lines)
        else:
            text = re.sub(r"\s+", " ", raw).strip()

        if "; " in text or " o " in text:
            parts = re.split(r";|\so\s", text)
            parts = [p.strip(" .") for p in parts if p.strip()]
            if parts:
                return "\n".join(f"- {p}" for p in parts)
        return text

    def _normalize_table(self, piece: str) -> str:
        rows = []
        text = re.sub(r"\s+", " ", piece.replace("|", " "))

        # Regex: Mã môn (chữ + số) + Tên môn + TC + LT + TH
        matches = re.findall(r"([A-Z]{2,}\d+)\s+([^0-9]+?)\s+(\d+)\s+(\d+)\s+(\d+)", text)
        for m in matches:
            ma, ten, tc, lt, th = m
            rows.append((ma, ten.strip(), tc, lt, th))

        if not rows:
            return piece.strip()

        md = "| Mã môn | Tên môn học | TC | LT | TH |\n"
        md += "|--------|-------------|----|----|----|\n"
        for r in rows:
            md += f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |\n"
        return md.strip()

    def format_context(self, chunks: List[Dict[str, Any]]) -> str:
        buf, total = [], 0
        for i, c in enumerate(chunks[:self.max_items]):
            piece = (c.get("content") or "").strip()
            if not piece:
                continue
            if total + len(piece) > self.max_chars:
                break
            if "|" in piece and re.search(r"[A-Z]{2,}\d+", piece):
                piece_fmt = self._normalize_table(piece)
            else:
                piece_fmt = self._normalize_text(piece)
            buf.append(piece_fmt)
            total += len(piece)
        return "\n\n".join(buf)
