from __future__ import annotations
import logging
import os
from typing import Iterable, List
from langchain_core.documents import Document
from .config.FPTCloud import RerankerModelConfig as cfg
from litellm import OpenAI

logger = logging.getLogger(__name__)

FPT_RERANKER_API_KEY = os.getenv("FPT_RERANKER_API_KEY") or os.getenv("FPT_EMBEDDING_API_KEY")

class FPTReranker:
    """
    FPT Cloud reranker for improving document retrieval relevance.
    
    Reranks a list of documents based on their semantic relevance to a query
    using FPT Cloud's reranking API via LiteLLM.
    
    Args:
        model_name: Name of the reranking model (default: bge-reranker-v2-m3)
        top_n: Number of top documents to return after reranking (default: 3)
        max_chars: Maximum characters per document, truncates if exceeded (default: 120000)
        
    Raises:
        ValueError: If FPT_RERANKER_API_KEY environment variable is not set
    """
    
    def __init__(
        self,
        model_name: str,
        top_n: int,
        max_chars: int = cfg.DEFAULT_MAX_CHARS,
    ):
        if not FPT_RERANKER_API_KEY:
            raise ValueError(
                "FPT reranker API key missing. "
                "Set FPT_RERANKER_API_KEY or reuse FPT_EMBEDDING_API_KEY."
            )
        self.model_name = model_name
        self.max_documents = max(1, cfg.DEFAULT_MAX_DOCS)
        self.top_n = max(1, top_n)
        self.max_chars = max(0, max_chars)
        self._truncate_warned = False
        self.client = OpenAI(api_key=FPT_RERANKER_API_KEY, base_url=cfg.DEFAULT_BASE_URL)

    def _prepare_doc(self, text: str) -> str:
        """
        Prepare document text for reranking by truncating if necessary.
        
        Args:
            text: Document text to prepare
            
        Returns:
            Stripped and optionally truncated text
        """
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
        """
        Rerank documents based on relevance to query.
                
        Args:
            query: Search query to rank documents against
            documents: Iterable of LangChain Document objects to rerank
            
        Returns:
            List of top_n most relevant documents in descending relevance order.
            Returns empty list if no documents provided.
            
        Raises:
            RuntimeError: If API request fails
        """

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
            response = self.client._client.post(
                f"{cfg.DEFAULT_BASE_URL}/v1/rerank",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.client.api_key}",
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"FPT reranker request failed: {e}")
        
        result = response.json()
        results = result.get("results", [])       
        reranked_docs: List[Document] = []
        for item in results:
            idx = item.get("index")
            if idx is not None and 0 <= idx < len(limited_docs):
                reranked_docs.append(limited_docs[idx])
        
        return reranked_docs