from qdrant_client import QdrantClient, models
from ..config.Qdrant import QdrantConfig as cfg
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from ..EmbeddingService.DenseEncoder import get_encoder
from ..EmbeddingService.SparseEncoder import FastEmbedSparseEncoder
from langchain_core.documents import Document
from typing import List
from langchain_community.vectorstores.utils import filter_complex_metadata

class QdrantBase:
    COLLECTION_NAME = cfg.QDRANT_COLLECTION_NAME
    VECTOR_NAME = str(cfg.QDRANT_VECTOR_NAME)
    SPARSE_VECTOR_NAME = str(cfg.QDRANT_SPARSE_VECTOR_NAME)
    BATCH_SIZE = cfg.QDRANT_BATCH_SIZE
    UPSERT_BATCH_SIZE = cfg.QDRANT_UPSERT_BATCH_SIZE
    SEARCH_TOP_K = cfg.QDRANT_SEARCH_TOP_K

    def __init__(self, api_key: str, url: str):
        self.api_key = api_key
        self.url = url
        self.__client = self.__initialize_client()
        self.__encoder = get_encoder()
        self.__sparse_encoder = FastEmbedSparseEncoder()
        self.__vector_store = self.__initialize_vector_store()

    def __initialize_client(self) -> QdrantClient:
        return QdrantClient(url=self.url, api_key=self.api_key)
    
    def __initialize_vector_store(self, mode: RetrievalMode = RetrievalMode.HYBRID) -> QdrantVectorStore:
        return QdrantVectorStore(
            client=self.__client,
            collection_name=self.COLLECTION_NAME,
            embedding=self.__encoder,
            vector_name=self.VECTOR_NAME,
            retrieval_mode=mode,
            sparse_embedding=self.__sparse_encoder,
            sparse_vector_name=self.SPARSE_VECTOR_NAME,
        )
    
    def __add_documents(self, documents: List[Document]) -> None:
        for i in range(0, len(documents), self.BATCH_SIZE):
            batch = documents[i : i + self.BATCH_SIZE]
            prepared = [
                Document(page_content=doc.page_content, metadata=dict(doc.metadata or {}))
                for doc in batch
            ]
            prepared = filter_complex_metadata(prepared)
            if not prepared:
                continue

            texts = [(doc.page_content or "") for doc in prepared]
            sparse_vectors = self.__sparse_encoder.embed_documents(texts)
            dense_vectors = self.__encoder.embed_documents(texts)

            points = []
            for idx, doc in enumerate(prepared):
                payload = {
                    "page_content": doc.page_content
                }
                payload.update(doc.metadata or {})
                points.append(
                    models.PointStruct(
                        id=str(doc.metadata.get("element_id")),
                        vector={
                            self.VECTOR_NAME: dense_vectors[idx],
                            self.SPARSE_VECTOR_NAME: models.SparseVector(
                                indices=sparse_vectors[idx].indices,
                                values=sparse_vectors[idx].values,
                            ),
                        },
                        payload=payload,
                    )
                )
            for start in range(0, len(points), self.UPSERT_BATCH_SIZE):
                chunk_points = points[start : start + self.UPSERT_BATCH_SIZE]
                self.__client.upsert(
                    collection_name=self.COLLECTION_NAME,
                    points=chunk_points,
                    wait=True,
                )
    
    def build_index(self, documents: List[Document]) -> None:
        self.__add_documents(documents)

    def clear_collection(self) -> None:
        """Delete the entire collection and recreate it"""
        try:
            self.__client.delete_collection(collection_name=self.COLLECTION_NAME)
        except Exception as e:
            raise RuntimeError(f"Failed to delete collection: {e}")
    
    def delete_all_points(self) -> None:
        """Delete all points in the collection but keep the collection structure"""
        try:
            self.__client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[]
                    )
                ),
                wait=True
            )
        except Exception as e:
            raise RuntimeError(f"Failed to delete all points: {e}")

    def search(self, query: str, k: int = SEARCH_TOP_K) -> List[Document]:
        search_params = models.SearchParams(
            hnsw_ef=256,
        )
        
        results = self.__vector_store.similarity_search(query, k=k, search_params=search_params, score_threshold=0.3)
        return results