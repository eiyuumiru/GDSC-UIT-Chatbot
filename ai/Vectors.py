from __future__ import annotations

import gc
import os
import uuid
from typing import List, Optional

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from langchain_community.vectorstores.utils import filter_complex_metadata
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)
from tqdm import tqdm
from .config.Qdrant import QdrantConfig as cfg

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "uit_edu")
QDRANT_PREFER_GRPC = os.getenv("QDRANT_PREFER_GRPC", "").lower() in {"1", "true", "yes"}
QDRANT_VECTOR_NAME = os.getenv("QDRANT_VECTOR_NAME", cfg.QDRANT_VECTOR_NAME)
QDRANT_SPARSE_VECTOR_NAME = os.getenv("QDRANT_SPARSE_VECTOR_NAME", cfg.QDRANT_SPARSE_VECTOR_NAME)
QDRANT_UPSERT_BATCH = max(1, int(os.getenv("QDRANT_UPSERT_BATCH", str(cfg.QDRANT_UPSERT_BATCH_SIZE))))


def _make_client(
    url: Optional[str] = None,
    api_key: Optional[str] = None,
    prefer_grpc: Optional[bool] = None,
) -> QdrantClient:
    client_kwargs: dict[str, object] = {
        "url": url or QDRANT_URL,
    }
    if not client_kwargs["url"]:
        raise ValueError(
            "QDRANT_URL is not configured. Please set the environment variable "
            "or pass the 'url' argument pointing to your Qdrant instance."
        )
    api_key_value = api_key if api_key is not None else QDRANT_API_KEY
    if api_key_value:
        client_kwargs["api_key"] = api_key_value
    pref = QDRANT_PREFER_GRPC if prefer_grpc is None else prefer_grpc
    if pref:
        client_kwargs["prefer_grpc"] = True
    return QdrantClient(**client_kwargs)


def _make_store(
    encoder,
    collection_name: str,
    client: Optional[QdrantClient] = None,
    retrieval_mode: str = "hybrid",
    sparse_encoder=None,
) -> QdrantVectorStore:
    active_client = client or _make_client()
    return QdrantVectorStore(
        client=active_client,
        collection_name=collection_name,
        embedding=encoder,
        vector_name=QDRANT_VECTOR_NAME,
        retrieval_mode=retrieval_mode,
        sparse_embedding=sparse_encoder,
        sparse_vector_name=QDRANT_SPARSE_VECTOR_NAME,
    )


def _probe_dense_dimension(encoder) -> int:
    probe = encoder.embed_query("__dimension_probe__")
    if not probe:
        raise ValueError(
            "Dense encoder returned an empty vector while probing dimensions. "
            "Verify the FPT embedding credentials and model configuration."
        )
    return len(probe)


def _ensure_collection(
    client: QdrantClient,
    collection_name: str,
    encoder,
    sparse_encoder,
) -> None:
    try:
        client.get_collection(collection_name=collection_name)
        return
    except Exception:
        pass

    dense_size = _probe_dense_dimension(encoder)
    vectors_config = {
        QDRANT_VECTOR_NAME: VectorParams(
            size=dense_size,
            distance=Distance.COSINE,
        )
    }
    sparse_vectors_config = None
    if sparse_encoder is not None:
        sparse_vectors_config = {
            QDRANT_SPARSE_VECTOR_NAME: SparseVectorParams(
                index=SparseIndexParams(),
            )
        }

    client.create_collection(
        collection_name=collection_name,
        vectors_config=vectors_config,
        sparse_vectors_config=sparse_vectors_config,
    )


def build_index(
    chunks: List[Document],
    encoder,
    *,
    sparse_encoder=None,
    collection_name: str = QDRANT_COLLECTION,
    batch_size: int = 64,
    show_progress: bool = True,
    clear_existing: bool = True,
    url: Optional[str] = None,
    api_key: Optional[str] = None,
    prefer_grpc: Optional[bool] = None,
) -> QdrantVectorStore:
    client = _make_client(url=url, api_key=api_key, prefer_grpc=prefer_grpc)

    if clear_existing:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

    _ensure_collection(
        client=client,
        collection_name=collection_name,
        encoder=encoder,
        sparse_encoder=sparse_encoder,
    )

    db = _make_store(
        encoder=encoder,
        collection_name=collection_name,
        client=client,
        retrieval_mode="hybrid" if sparse_encoder else "dense",
        sparse_encoder=sparse_encoder,
    )

    total = len(chunks)
    if total == 0:
        return db

    bar = tqdm(
        total=total,
        desc="Embedding & Indexing",
        unit="doc",
        dynamic_ncols=True,
        mininterval=0.2,
        ascii=True,
        disable=not show_progress,
    )

    for i in range(0, total, batch_size):
        batch = chunks[i: i + batch_size]
        prepared = [
            Document(page_content=doc.page_content, metadata=dict(doc.metadata or {}))
            for doc in batch
        ]
        clean_batch = filter_complex_metadata(prepared)
        
        if clean_batch:
            if sparse_encoder is not None:
                texts = [(doc.page_content or "") for doc in clean_batch]
                dense_vectors = encoder.embed_documents(texts)
                sparse_vectors = sparse_encoder.embed_documents(texts)

                points: List[PointStruct] = []
                for idx, doc in enumerate(clean_batch):
                    payload = {"page_content": doc.page_content or ""}
                    payload.update(doc.metadata or {})
                    points.append(
                        PointStruct(
                            id=str(uuid.uuid4()),
                            vector={
                                QDRANT_VECTOR_NAME: dense_vectors[idx],
                                QDRANT_SPARSE_VECTOR_NAME: SparseVector(
                                    indices=sparse_vectors[idx].indices,
                                    values=sparse_vectors[idx].values,
                                ),
                            },
                            payload=payload,
                        )
                    )
                for start in range(0, len(points), QDRANT_UPSERT_BATCH):
                    chunk_points = points[start : start + QDRANT_UPSERT_BATCH]
                    client.upsert(
                        collection_name=collection_name,
                        points=chunk_points,
                        wait=True,
                    )
            else:
                db.add_documents(clean_batch)
        
        gc.collect()
        bar.update(len(batch))

    bar.close()
    return db

def load_index(
    encoder,
    *,
    sparse_encoder=None,
    collection_name: str = QDRANT_COLLECTION,
    url: Optional[str] = None,
    api_key: Optional[str] = None,
    prefer_grpc: Optional[bool] = None,
) -> QdrantVectorStore:
    client = _make_client(url=url, api_key=api_key, prefer_grpc=prefer_grpc)
    retrieval_mode = "hybrid" if sparse_encoder else "dense"
    return _make_store(
        encoder=encoder,
        collection_name=collection_name,
        client=client,
        retrieval_mode=retrieval_mode,
        sparse_encoder=sparse_encoder,
    )