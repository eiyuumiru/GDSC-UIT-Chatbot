from fastembed import SparseTextEmbedding
from langchain_qdrant import SparseEmbeddings, SparseVector

class FastEmbedSparseEncoder(SparseEmbeddings):
    MODEL_NAME = "Qdrant/bm42-all-minilm-l6-v2-attentions"
    BATCH_SIZE = 32

    def __init__(self, model_name: str = MODEL_NAME, batch_size: int = BATCH_SIZE):
        self.model = SparseTextEmbedding(model_name=model_name)
        self.batch_size = batch_size

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        if not texts:
            return []
        results = []
        for idx in range(0, len(texts), self.batch_size):
            batch = texts[idx : idx + self.batch_size]
            for embedding in self.model.embed(batch):
                results.append(embedding)
        return results

    def embed_query(self, text: str) -> SparseVector:
        result = self.embed_documents([text])
        if result:
            return result[0]
        return SparseVector(indices=[], values=[])