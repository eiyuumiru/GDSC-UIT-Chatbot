from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Sequence

import httpx
from langchain_core.embeddings import Embeddings


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("FPT_EMBEDDING_MODEL", "Vietnamese_Embedding")
DEFAULT_BASE_URL = os.getenv("FPT_EMBEDDING_BASE_URL", "https://mkp-api.fptcloud.com")
DEFAULT_DIMENSIONS = _get_int_env("FPT_EMBEDDING_DIMENSIONS", 0)
DEFAULT_FORMAT = os.getenv("FPT_EMBEDDING_FORMAT", "float")
DEFAULT_INPUT_TYPE = os.getenv("FPT_EMBEDDING_INPUT_TYPE", "passage")
DEFAULT_TRUNCATE = os.getenv("FPT_EMBEDDING_TRUNCATE", "none")
DEFAULT_TIMEOUT = _get_float_env("FPT_EMBEDDING_TIMEOUT", 30.0)
DEFAULT_BATCH_SIZE = _get_int_env("FPT_EMBEDDING_BATCH_SIZE", 16)
DEFAULT_MAX_INPUT_CHARS = _get_int_env("FPT_EMBEDDING_MAX_CHARS", 120_000)
API_KEY_ENV = os.getenv("FPT_EMBEDDING_API_KEY")


class FPTMarketplaceEmbeddings(Embeddings):

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        dimensions: int = DEFAULT_DIMENSIONS,
        encoding_format: str = DEFAULT_FORMAT,
        input_type: str = DEFAULT_INPUT_TYPE,
        input_text_truncate: str = DEFAULT_TRUNCATE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
    ):
        self.api_key = api_key or API_KEY_ENV
        if not self.api_key:
            raise ValueError("FPT_EMBEDDING_API_KEY is not set. Please add it to your environment.")
        self.model_name = model_name or DEFAULT_MODEL
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        if not self.base_url:
            raise ValueError("FPT embedding base URL is missing.")
        self.dimensions = dimensions
        self.encoding_format = encoding_format
        self.input_type = input_type
        self.input_text_truncate = input_text_truncate
        self.batch_size = max(1, batch_size)
        self.timeout = timeout
        self.max_input_chars = max(0, max_input_chars)
        self._endpoint = "/v1/embeddings"
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        self._truncate_warned = False

    def _prepare_text(self, text: str) -> str:
        normalized = (text or "").strip()
        if self.max_input_chars and len(normalized) > self.max_input_chars:
            if not self._truncate_warned:
                logger.warning(
                    "Embedding input exceeded %s characters. Truncating to comply with FPT limits. "
                    "Set FPT_EMBEDDING_MAX_CHARS to adjust this threshold.",
                    self.max_input_chars,
                )
                self._truncate_warned = True
            return normalized[: self.max_input_chars]
        return normalized

    def _request_embeddings(self, inputs: Sequence[str]) -> List[List[float]]:
        if not inputs:
            return []
        payload: dict[str, object] = {
            "model": self.model_name,
            "input": list(inputs),
            "encoding_format": self.encoding_format,
            "input_type": self.input_type,
        }
        if self.dimensions and self.dimensions > 0:
            payload["dimensions"] = self.dimensions
        if self.input_text_truncate:
            payload["input_text_truncate"] = self.input_text_truncate
        try:
            response = self._client.post(self._endpoint, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body_preview = ""
            try:
                body_preview = exc.response.text[:500]
            except Exception:
                pass
            raise RuntimeError(
                "FPT embedding API call failed with "
                f"{exc.response.status_code} {exc.response.reason_phrase}. "
                "Please double-check FPT_EMBEDDING_API_KEY, model permissions, "
                "and remaining quota. "
                f"Response snippet: {body_preview}"
            ) from exc
        data = response.json().get("data", [])
        if not isinstance(data, list):
            raise ValueError("Unexpected response format from FPT embedding API.")
        embeddings: List[List[float]] = []
        for item in data:
            embedding = item.get("embedding") if isinstance(item, dict) else None
            if embedding is None:
                raise ValueError("Missing embedding vector in FPT API response.")
            embeddings.append(list(embedding))
        return embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        vectors: List[List[float]] = []
        for idx in range(0, len(texts), self.batch_size):
            batch = [self._prepare_text(text or "") for text in texts[idx : idx + self.batch_size]]
            vectors.extend(self._request_embeddings(batch))
        return vectors

    def embed_query(self, text: str) -> List[float]:
        result = self.embed_documents([text])
        return result[0] if result else []

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def __del__(self) -> None:
        self.close()


class STEncoder(Embeddings):

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        normalize: bool | None = None,
        max_seq_length: int = 2048,
        show_tqdm: bool | None = None,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        dimensions: int = DEFAULT_DIMENSIONS,
        input_type: str = DEFAULT_INPUT_TYPE,
        input_text_truncate: str = DEFAULT_TRUNCATE,
        timeout: float = DEFAULT_TIMEOUT,
        max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
    ):
        self._impl = FPTMarketplaceEmbeddings(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            dimensions=dimensions,
            batch_size=batch_size,
            input_type=input_type,
            input_text_truncate=input_text_truncate,
            timeout=timeout,
            max_input_chars=max_input_chars,
        )
        self.max_seq_length = max_seq_length
        self._placeholder_config = {
            "device": device,
            "normalize": normalize,
            "show_tqdm": show_tqdm,
        }

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._impl.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._impl.embed_query(text)

    def close(self) -> None:
        self._impl.close()


def get_encoder(
    model_name: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
) -> Embeddings:
    return STEncoder(model_name=model_name, batch_size=batch_size, max_input_chars=max_input_chars)


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