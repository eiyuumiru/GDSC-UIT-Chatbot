from langchain_litellm import ChatLiteLLM, ChatLiteLLMRouter
from litellm.router import Router
import litellm
import os
import re
from ..config.Groq import GroqLLMConfig as cfg
from .KeyManager import key_manager
from typing import Optional


def _handle_litellm_failure(kwargs, exception, traceback_exception):
    """
    LiteLLM failure callback theo Groq error codes.
    
    Key-related errors (switch key):
    - 401: Unauthorized - invalid API key
    - 403: Forbidden - permission/revoked key
    - 429: Rate limit - cooldown then switch
    
    Non-key errors (don't switch):
    - 400, 404, 413, 422: Request errors
    - 5xx: Server errors
    """
    error_str = str(exception).lower()
    error_original = str(exception)
    
    # Extract error code if present
    error_code = None
    for code in ["401", "403", "429", "400", "404", "413", "422", "500", "502", "503"]:
        if code in error_original:
            error_code = int(code)
            break
    
    # 429 - Rate limit: cooldown and switch
    if error_code == 429 or ("rate" in error_str and "limit" in error_str):
        retry_after = 60
        match = re.search(r"retry.?after[:\s]+(\d+)", error_original, re.IGNORECASE)
        if match:
            retry_after = int(match.group(1))
        print(f"[GroqBase] 429 Rate limit, cooldown {retry_after}s")
        key_manager.mark_cooldown(retry_after)
    
    # 401 - Unauthorized: invalid key, switch
    elif error_code == 401 or "unauthorized" in error_str:
        print(f"[GroqBase] 401 Unauthorized, switching key")
        key_manager.mark_invalid()
    
    # 403 - Forbidden: revoked/permission issue, switch
    elif error_code == 403 or "forbidden" in error_str:
        print(f"[GroqBase] 403 Forbidden, switching key")
        key_manager.mark_invalid()
    
    # Invalid key message without code
    elif "invalid" in error_str and ("key" in error_str or "api_key" in error_str):
        print(f"[GroqBase] Invalid API key, switching key")
        key_manager.mark_invalid()
    
    # 5xx Server errors: don't switch key, server issue
    elif error_code and error_code >= 500:
        print(f"[GroqBase] {error_code} Server error, will retry same key")
    
    # Other client errors (400, 404, etc): don't switch, request issue
    else:
        print(f"[GroqBase] Error: {error_original[:100]}")


# Register the callback with LiteLLM
litellm.failure_callback = [_handle_litellm_failure]


class GroqBase:
    """
    Base class for creating Groq LLM instances using LiteLLM.
    
    Uses KeyManager for multi-key rotation with cooldown on rate limits.
    Uses LiteLLM Router for model fallback (llama ↔ gpt-oss).
    """

    MODEL_LIST = cfg.DEFAULT_FALLBACK_MODEL
    MAX_RETRIES = cfg.DEFAULT_MAX_RETRIES

    def create_llm(self, model: str, temperature: float, max_tokens: Optional[int], timeout: float) -> ChatLiteLLMRouter:
        """
        Create a Groq LLM instance via LiteLLM with auto key rotation.
        
        Args:
            model: Groq model name (default: openai/gpt-oss-120b)
            temperature: Sampling temperature (default: 0.5)
            max_tokens: Maximum tokens to generate (default: None)
            timeout: Request timeout in seconds
            
        Returns:
            ChatLiteLLMRouter instance configured for Groq
        """
        # Get current key from KeyManager
        api_key = key_manager.get_current_key()
        os.environ["GROQ_API_KEY"] = api_key
        
        litellm_router = Router(model_list=self.MODEL_LIST)
        return ChatLiteLLMRouter(
            router=litellm_router,
            model=f"groq/{model}",
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
            max_retries=self.MAX_RETRIES
        )