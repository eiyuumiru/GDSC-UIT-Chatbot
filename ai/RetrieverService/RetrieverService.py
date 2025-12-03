from __future__ import annotations
import os
from typing import Dict, Any, List
import json
import re
from ..EmbeddingService.DenseEncoder import get_encoder
from ..Reranker import FPTReranker
from langchain_core.tools import tool, BaseTool
from ..config.FPTCloud import RerankerModelConfig as cfg
from ..QdrantService.QdrantBase import QdrantBase

class RetrieverService:
    """
    Service for retrieving and ranking relevant documents from Qdrant vector store.
    
    Retrieves candidate documents using hybrid search (dense + sparse vectors),
    then reranks them using FPT Reranker for optimal relevance.
    """
    def __init__(self, model_name = cfg.DEFAULT_MODEL, top_n: int = cfg.DEFAULT_TOP_N):
        self._ENC = self.__init_Encoder()
        self._RERANKER = self.__init_Reranker(model_name=model_name, top_n=top_n)
        self.qdrant = self.__init_Qdrant()

    def __init_Qdrant(self):
        return QdrantBase(
            api_key=os.getenv("QDRANT_API_KEY", ""),
            url=os.getenv("QDRANT_URL", ""),
        )

    def __init_Encoder(self):
        return get_encoder()
    
    def __init_Reranker(self, model_name: str, top_n: int) -> FPTReranker:
        return FPTReranker(model_name=model_name, top_n=top_n)
    
    def _retrieve_impl(self, query: str) -> tuple[str, List[Dict[str, Any]]]:
        candidate_docs = self.qdrant.search(query, k=20)
        ranked_docs = self._RERANKER.rerank(query=query, documents=candidate_docs)
        results: List[Dict[str, Any]] = [
            {
                "content": doc.page_content,
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
