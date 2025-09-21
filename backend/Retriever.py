from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Sequence, List
from collections.abc import Sequence
from langchain_community.retrievers import BM25Retriever
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain.retrievers import EnsembleRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

_TOKEN_PATTERN = re.compile(r"[\w\-À-ỹ]+", re.UNICODE)

def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [tok for tok in _TOKEN_PATTERN.findall(text.lower()) if tok]

@dataclass
class HybridCandidate:
    doc: Document
    lexical_rank: int | None = None
    lexical_score: float | None = None
    dense_rank: int | None = None
    dense_score: float | None = None
    rrf_score: float = 0.0
    term_hits: int = 0
    lexical_norm: float = 0.0
    dense_norm: float = 0.0
    term_norm: float = 0.0
    coarse_score: float = 0.0

# ==============================
# TermHit Retriever (custom)
# ==============================
class TermHitRetriever(BaseRetriever):
    """Retriever phụ để tính term_hits dựa trên keyword match trong content/metadata.

    Implemented as a field-based class so it's compatible with BaseRetriever's
    dataclass/pydantic-style initialization. Do not override __init__.
    """
    chunks: Sequence[Document]

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> List[Document]:
        tokens = _tokenize(query)
        hit_tokens = [tok for tok in tokens if len(tok) > 2 or tok.isdigit()]
        scored_docs = []

        for doc in self.chunks:
            meta = doc.metadata or {}
            haystacks = [(doc.page_content or "").lower()]
            for key in ("section_path", "source", "h1", "h2", "h3", "h4", "title"):
                value = meta.get(key)
                if value:
                    haystacks.append(str(value).lower())
            combined = " ".join(haystacks)

            hits = 0
            for token in hit_tokens:
                hits += combined.count(token)

            if hits > 0:
                # Ghi lại score vào metadata để EnsembleRetriever normalize
                scored_doc = Document(
                    page_content=doc.page_content,
                    metadata={**meta, "term_hits": hits},
                )
                scored_docs.append(scored_doc)

        return scored_docs

def make_hybrid_retriever(
    chunks: Sequence[Document],
    db,  # VectorStore (vd: Chroma, FAISS...)
    k: int = 10,
    weights: list[float] = [0.6, 0.3, 0.1],
) -> EnsembleRetriever:
    """
    Tạo HybridRetriever dùng EnsembleRetriever:
      - BM25 (lexical)
      - Dense retriever (vectorstore)
      - TermHitRetriever (match từ khóa trong content/metadata)
    """

    # BM25 lexical retriever
    bm25 = BM25Retriever.from_documents(chunks, preprocess_func=_tokenize)
    bm25.k = k

    # Dense retriever từ vectorstore
    dense = db.as_retriever(search_kwargs={"k": k})

    # TermHit retriever (instantiate with keyword to match field-based init)
    term = TermHitRetriever(chunks=chunks)

    # Ensemble retriever (LangChain tự normalize + weighted sum)
    hybrid = EnsembleRetriever(
        retrievers=[bm25, dense, term],
        weights=weights,
    )
    return hybrid

def docs_from_chroma(db) -> list[Document]:
    collection = getattr(db, "_collection", None)
    if collection is None:
        return []
    data = collection.get(include=["documents", "metadatas"])
    docs = []
    ids = data.get("ids", [])
    texts = data.get("documents", [])
    metas = data.get("metadatas", [])
    for doc_id, text, meta in zip(ids, texts, metas):
        info = dict(meta or {})
        info.setdefault("_id", doc_id)
        docs.append(Document(page_content=text or "", metadata=info))
    return docs