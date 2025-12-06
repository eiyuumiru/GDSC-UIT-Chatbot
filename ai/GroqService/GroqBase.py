from langchain_litellm import ChatLiteLLM, ChatLiteLLMRouter
from litellm.router import Router
import os
from ..config.Groq import GroqLLMConfig as cfg
from typing import Optional

class GroqBase:
    """
    Base class for creating Groq LLM instances using LiteLLM.
    
    Provides a factory method to initialize ChatLiteLLM with Groq API configuration.
    """

    MODEL_LIST = cfg.DEFAULT_FALLBACK_MODEL
    MAX_RETRIES = cfg.DEFAULT_MAX_RETRIES

    def create_llm(self, api_key: str, model: str, temperature: float, max_tokens: Optional[int], timeout: float) -> ChatLiteLLM:
        """
        Create a Groq LLM instance via LiteLLM.
        
        Args:
            api_key: Groq API key. Will be set as GROQ_API_KEY environment variable
            model: Groq model name (default: llama-3.3-70b-versatile)
            temperature: Sampling temperature (default: 0.2)
            max_tokens: Maximum tokens to generate (default: None)
            
        Returns:
            ChatLiteLLM instance configured for Groq
        """
        if api_key:
            os.environ["GROQ_API_KEY"] = api_key
        litellm_router = Router(model_list=self.MODEL_LIST)
        return ChatLiteLLMRouter(router=litellm_router, model=f"groq/{model}", temperature=temperature, max_tokens=max_tokens, request_timeout=timeout, max_retries=self.MAX_RETRIES)