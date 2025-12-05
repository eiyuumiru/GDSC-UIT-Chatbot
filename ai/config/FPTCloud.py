class FPTCloudConfig:
    DEFAULT_BASE_URL = "https://mkp-api.fptcloud.com"

class EmbeddingModelConfig(FPTCloudConfig):
    DEFAULT_MODEL = "openai/Vietnamese_Embedding"
    DEFAULT_DIMENSIONS = 1024
    DEFAULT_FORMAT = "float"
    DEFAULT_INPUT_TYPE = "passage"
    DEFAULT_TRUNCATE = "none"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_BATCH_SIZE = 16
    DEFAULT_MAX_INPUT_TOKEN = 8192
    DEFAULT_ENCODING_FORMAT = "float"
    DEFAULT_DIMENSIONS = 1024
    DEFAULT_INPUT_TEXT_TRUNCATE = "none"
    DEFAULT_INPUT_TYPE = "passage"

class RerankerModelConfig(FPTCloudConfig):
    DEFAULT_MODEL = "bge-reranker-v2-m3"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MAX_DOCS = 200
    DEFAULT_MAX_CHARS = 120_000
    DEFAULT_TOP_N = 4
