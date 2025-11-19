from __future__ import annotations
import os
from typing import Dict, Any, List
import json
import re
import logging
from .EmbeddingManager import get_encoder, get_sparse_encoder
from .Vectors import load_index as load_vec, build_index as build_qdrant_index
from .Retriever import docs_from_qdrant, make_hybrid_retriever
from .Loaders import load_markdown
from .Splitters import split_markdown
from .Reranker import FPTReranker
from langchain_core.tools import tool, BaseTool
from .config.FPTCloud import RerankerModelConfig as cfg

logger = logging.getLogger(__name__)

class RetrieverService:
    def __init__(self, model_name = cfg.DEFAULT_MODEL, top_n: int = cfg.DEFAULT_TOP_N, weights: list[float] = [0.85, 0.15], use_server_sparse: bool = True):
        self.use_server_sparse = use_server_sparse
        self._ENC = self.__init_Encoder()
        self._SPARSE_ENC = self.__init_SparseEncoder() if use_server_sparse else None
        if self.use_server_sparse and self._SPARSE_ENC is None:
            self.use_server_sparse = False
        self._DB = self.__init_DB()
        self._CHUNKS_FOR_BM25 = self.__init_ChunksForBM25()
        self._RERANKER = self.__init_Reranker(model_name=model_name, top_n=top_n)
        self.hybrid_retriever = self.__init_HybridRetriever(weights=weights, k=top_n)

    def __init_DB(self):
        return load_vec(
            encoder=self._ENC,
            sparse_encoder=self._SPARSE_ENC if self.use_server_sparse else None,
        )

    def __init_Encoder(self):
        return get_encoder()
    
    def __init_SparseEncoder(self):
        logger.info("Initializing sparse encoder for server-side hybrid search")
        return get_sparse_encoder(batch_size=32)

    def __init_ChunksForBM25(self):
        return docs_from_qdrant(self._DB)

    def __init_Reranker(self, model_name: str, top_n: int) -> FPTReranker:
        return FPTReranker(model_name=model_name, top_n=top_n)
    
    def __init_HybridRetriever(self, weights: list[float] = [0.85, 0.15], k: int = 6):
        return make_hybrid_retriever(
            self._CHUNKS_FOR_BM25,
            self._DB,
            k=k,
            weights=weights,
            use_server_sparse=self.use_server_sparse,
        )

    def _retrieve_impl(self, query: str) -> tuple[str, List[Dict[str, Any]]]:
        candidate_docs = self.hybrid_retriever.invoke(query)
        ranked_docs = self._RERANKER.rerank(query=query, documents=candidate_docs)
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
        """Retrieve UIT knowledge snippets for the current query."""
        return svc._retrieve_impl(query)
    return _retrieve


def build_index(
    *,
    data_dir: str = "ai/dataset",
    collection_name: str | None = None,
    clear_existing: bool = True,
    batch_size: int = 64,
    show_progress: bool = True,
) -> None:
    docs = load_markdown(data_dir)
    encoder = get_encoder()
    sparse_encoder = get_sparse_encoder()
    chunks = split_markdown(docs, encoder, show_progress=show_progress)
    build_qdrant_index(
        chunks,
        encoder,
        sparse_encoder=sparse_encoder,
        collection_name=collection_name or os.getenv("QDRANT_COLLECTION", "uit_edu"),
        batch_size=batch_size,
        show_progress=show_progress,
        clear_existing=clear_existing,
    )

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
