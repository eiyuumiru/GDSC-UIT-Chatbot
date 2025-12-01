from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Sequence, List, Optional, Any
from collections.abc import Sequence as ABCSequence
from langchain_community.retrievers import BM25Retriever
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

_TOKEN_PATTERN = re.compile(r"[\w\-À-ỹ]+", re.UNICODE)

def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [tok for tok in _TOKEN_PATTERN.findall(text.lower()) if tok]

class TermHitRetriever(BaseRetriever):
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
                scored_doc = Document(
                    page_content=doc.page_content,
                    metadata={**meta, "term_hits": hits},
                )
                scored_docs.append(scored_doc)

        return scored_docs

def make_hybrid_retriever(
    chunks: ABCSequence[Document],
    db,
    k: int = 10,
    weights: list[float] = [0.85, 0.15],
    use_server_sparse: bool = True,
) -> EnsembleRetriever:
    dense = db.as_retriever(search_kwargs={"k": k})
    term = TermHitRetriever(chunks=chunks)
    if use_server_sparse:
        hybrid = EnsembleRetriever(
            retrievers=[dense, term],
            weights=weights,
        )
    else:
        bm25 = BM25Retriever.from_documents(list(chunks), preprocess_func=_tokenize)
        bm25.k = k
        hybrid = EnsembleRetriever(
            retrievers=[bm25, dense, term],
            weights=[0.3, 0.6, 0.1],
        )
    return hybrid

def docs_from_qdrant(db, batch_size: int = 256) -> list[Document]:
    client = getattr(db, "client", None)
    collection_name: Optional[str] = getattr(db, "collection_name", None) or getattr(db, "_collection_name", None)
    if client is None or not collection_name:
        return []

    docs: list[Document] = []
    offset: Any = None

    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            with_payload=True,
            with_vectors=False,
            limit=batch_size,
            offset=offset,
        )
        if not points:
            break
        for point in points:
            payload = dict(getattr(point, "payload", {}) or {})
            text = payload.pop("page_content", payload.pop("text", "")) or ""
            nested_meta = payload.pop("metadata", {})
            if isinstance(nested_meta, dict):
                metadata = {**payload, **nested_meta}
            else:
                metadata = payload
            point_id = getattr(point, "id", None)
            if point_id is not None:
                metadata.setdefault("_id", point_id)
            docs.append(Document(page_content=text, metadata=metadata))
        if offset is None:
            break
    return docs