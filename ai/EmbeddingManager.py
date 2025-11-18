from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from typing import List
from langchain_core.embeddings import Embeddings
from .config.FPTCloud import EmbeddingModelConfig as cfg
from litellm import embedding

logger = logging.getLogger(__name__)

API_KEY_ENV = os.getenv("FPT_EMBEDDING_API_KEY")

class FPTEmbedding(Embeddings):
    """
    FPT Cloud embedding model wrapper using LiteLLM.
    
    Provides text embedding functionality via FPT Cloud API, compatible with
    LangChain's Embeddings interface.

    Args:
        model_name: Name of the embedding model (default: Vietnamese_Embedding)
        max_seq_length: Maximum sequence length for input texts
        api_key: FPT Cloud API key. Falls back to FPT_EMBEDDING_API_KEY env var
        base_url: Base URL for FPT Cloud API
    """
    
    def __init__(
        self,
        model_name: str = cfg.DEFAULT_MODEL,
        max_seq_length: int = 2048,
        api_key: str | None = None,
        base_url: str = cfg.DEFAULT_BASE_URL,
    ):
        self.model_name = model_name
        self.base_url = base_url
        self.max_seq_length = max_seq_length
        self.api_key = api_key or API_KEY_ENV

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple documents.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (List[List[float]]). Returns empty list on error.
        """
        try:
            response = embedding(
                model=cfg.DEFAULT_MODEL,
                input=texts,
                api_base=cfg.DEFAULT_BASE_URL,
                api_key=self.api_key,
                encoding_format=cfg.DEFAULT_ENCODING_FORMAT,
            )
        except Exception as e:
            logger.error("Error embedding documents: %s", e)
            return []
        results: dict = response.to_dict()
        result: List = [f.get("embedding", []) for f in results.get("data", [])]

        return result

    def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query text.
        
        Args:
            text: Query string to embed
            
        Returns:
            Embedding vector as List[float]. Returns empty list on error.
        """
        try:
            response = embedding(
                model=cfg.DEFAULT_MODEL,
                input=[text],
                api_base=cfg.DEFAULT_BASE_URL,
                api_key=self.api_key,
                encoding_format=cfg.DEFAULT_ENCODING_FORMAT,
            )
        except Exception as e:
            logger.error("Error embedding query: %s", e)
            return []
        results: dict = response.to_dict()
        result: List[dict] = results.get("data", [])
        return result[0].get("embedding", [])

def get_encoder(
    model_name: str = cfg.DEFAULT_MODEL,
    max_input_chars: int = cfg.DEFAULT_MAX_INPUT_CHARS,
) -> Embeddings:
    return FPTEmbedding(model_name=model_name)


class FastEmbedSparseEncoder:

    @dataclass
    class SparseVector:
        indices: List[int]
        values: List[float]

    def __init__(self, model_name: str = "Qdrant/bm42-all-minilm-l6-v2-attentions", batch_size: int = 32):
        from fastembed import SparseTextEmbedding
        self.model = SparseTextEmbedding(model_name=model_name)
        self.batch_size = batch_size

    def _convert_embedding(self, embedding) -> "FastEmbedSparseEncoder.SparseVector":
        indices = embedding.indices.tolist()
        values = embedding.values.tolist()
        return FastEmbedSparseEncoder.SparseVector(indices=indices, values=values)

    def embed_documents(self, texts: List[str]) -> List["FastEmbedSparseEncoder.SparseVector"]:
        if not texts:
            return []
        results = []
        for idx in range(0, len(texts), self.batch_size):
            batch = texts[idx : idx + self.batch_size]
            for embedding in self.model.embed(batch):
                results.append(self._convert_embedding(embedding))
        return results

    def embed_query(self, text: str) -> "FastEmbedSparseEncoder.SparseVector":
        result = self.embed_documents([text])
        if result:
            return result[0]
        return FastEmbedSparseEncoder.SparseVector(indices=[], values=[])


def get_sparse_encoder(
    model_name: str = "Qdrant/bm42-all-minilm-l6-v2-attentions",
    batch_size: int = 32,
) -> FastEmbedSparseEncoder:
    return FastEmbedSparseEncoder(model_name=model_name, batch_size=batch_size)

#Example usage
if __name__ == "__main__":
    encoder = get_encoder()
    texts = ["Xin chào", "Đây là một đoạn văn bản để kiểm tra embedding."]
    embeddings = encoder.embed_documents(texts)
    print(embeddings)