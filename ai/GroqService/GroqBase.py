from langchain_litellm import ChatLiteLLM
import os
from typing import Optional

class GroqBase:
    """
    Base class for creating Groq LLM instances using LiteLLM.
    
    Provides a factory method to initialize ChatLiteLLM with Groq API configuration.
    """
    
    def create_llm(self, api_key: str, model: str = "llama-3.3-70b-versatile", temperature: float = 0.2, max_tokens: Optional[int] = None) -> ChatLiteLLM:
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
        
        return ChatLiteLLM(model=f"groq/{model}",temperature=temperature,max_tokens=max_tokens)