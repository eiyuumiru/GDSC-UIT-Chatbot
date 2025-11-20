class QdrantConfig:
    COLLECTION_NAME = "uit_edu"
    QDRANT_VECTOR_NAME = "dense"
    QDRANT_SPARSE_VECTOR_NAME = "sparse"
    QDRANT_UPSERT_BATCH = 16
    QDRANT_PREFER_GRPC = True