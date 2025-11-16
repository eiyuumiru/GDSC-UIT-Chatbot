from __future__ import annotations
from typing import Dict, Any, List, Optional
import json
import re
import time
import logging
from .Loaders import load_markdown
from .Splitters import split_markdown
from .EmbeddingManager import get_encoder
from .Vectors import build_index as build_vec, load_index as load_vec
from .Retriever import docs_from_chroma, make_hybrid_retriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_core.tools import tool, BaseTool
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

logger = logging.getLogger(__name__)

class RetrieverService:
    def __init__(self, model_name = "jinaai/jina-reranker-v2-base-multilingual", top_n: int = 3, weights: list[float] = [0.3, 0.6, 0.1]):
        self.top_n = top_n
        self._ENC = self.__init_Encoder()
        self._DB = self.__init_DB()
        self._CHUNKS_FOR_BM25 = self.__init_ChunksForBM25()
        self._RERANKER: CrossEncoderReranker = self.__init_Reranker(model_name=model_name, top_n=top_n)
        self.hybrid_retriever = self.__init_HybridRetriever(weights=weights, k=top_n)

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

    def __init_Reranker(self, model_name: str = "jinaai/jina-reranker-v2-base-multilingual", top_n: int = 3) -> CrossEncoderReranker:
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
        logger.info("[retrieve] ranked_docs sample: %s", ranked_docs)

        results: List[Dict[str, Any]] = [
            {
                "source": doc.metadata.get("source", ""),
                "content": doc.page_content,
                "metadata": dict(doc.metadata or {}),
            }
            for doc in ranked_docs
        ]

        return query, results

def make_retrieve_tool(svc: RetrieverService) -> BaseTool:
    @tool(response_format="content_and_artifact")
    def _retrieve(query: str) -> tuple[str, List[Dict[str, Any]]]:
        return svc._retrieve_impl(query)
    return _retrieve

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

    def _stringify_cell(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return " ".join(value.split())
        if isinstance(value, (int, float)):
            return str(value)
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    def _render_table_snippet(self, payload: Any) -> str:
        if payload is None:
            return ""
        data = payload
        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except Exception:
                return ""
        rows: List[List[str]] = []
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                headers = list(data[0].keys())[:8]
                if headers:
                    rows.append([self._stringify_cell(h) for h in headers])
                for row in data[:8]:
                    rows.append([self._stringify_cell(row.get(h, "")) for h in headers])
            elif data and isinstance(data[0], list):
                for row in data[:8]:
                    rows.append([self._stringify_cell(cell) for cell in row[:8]])
            else:
                for item in data[:8]:
                    rows.append([self._stringify_cell(item)])
        elif isinstance(data, dict):
            rows.append([self._stringify_cell("key"), self._stringify_cell("value")])
            for key, value in list(data.items())[:8]:
                rows.append([self._stringify_cell(key), self._stringify_cell(value)])
        else:
            return ""
        trimmed_rows: List[List[str]] = []
        for row in rows:
            trimmed_row = []
            for cell in row[:8]:
                cell_text = cell
                if len(cell_text) > 80:
                    cell_text = cell_text[:77].rstrip() + "..."
                trimmed_row.append(cell_text)
            if any(trimmed_row):
                trimmed_rows.append(trimmed_row)
            if len(trimmed_rows) >= 8:
                break
        if not trimmed_rows:
            return ""
        return "\n".join(",".join(r) for r in trimmed_rows)

    def format_context(self, chunks: List[Dict[str, Any]]) -> str:
        buf: List[str] = []
        total = 0
        for chunk in chunks[:self.max_items]:
            piece = (chunk.get("content") or "").strip()
            if not piece:
                continue
            metadata = chunk.get("metadata") if isinstance(chunk, dict) else {}
            if not isinstance(metadata, dict):
                metadata = {}
            if metadata.get("is_table"):
                table_block = piece
                snippet = self._render_table_snippet(metadata.get("table_json"))
                if snippet:
                    table_block = f"{piece}\n\nCSV preview:\n{snippet}"
                if total + len(table_block) > self.max_chars:
                    break
                buf.append(table_block)
                total += len(table_block)
                continue
            piece_fmt = self._normalize_table(piece) if ("|" in piece and re.search(r"[A-Z]{2,}\d+", piece)) else self._normalize_text(piece)
            if total + len(piece_fmt) > self.max_chars:
                break
            buf.append(piece_fmt)
            total += len(piece_fmt)
        return "\n\n".join(buf)
