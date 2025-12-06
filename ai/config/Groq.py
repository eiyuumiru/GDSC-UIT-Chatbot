class GroqLLMConfig:
    DEFAULT_MODEL_NAME = "openai/gpt-oss-120b"
    DEFAULT_TEMPERATURE = 0.5
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_FALLBACK_MODEL = [
        {
            "model_name": "llama-3.3-70b-versatile",
            "litellm_params": {
                "model": "groq/llama-3.3-70b-versatile",
            },
        },
        {
            "model_name": "openai/gpt-oss-120b",
            "litellm_params": {
                "model": "groq/openai/gpt-oss-120b",
            },
        },
    ]
