"""
Groq API Key Manager with round-robin rotation and cooldown based on retry-after header.
"""
import os
import time
import threading
from typing import List, Optional


class GroqKeyManager:
    """
    Manages multiple Groq API keys with round-robin rotation and cooldown.
    
    Features:
    - Round-robin key selection
    - Cooldown based on retry-after header from 429 responses
    - Thread-safe operations
    - Remembers current key index across requests
    """
    
    _instance: Optional["GroqKeyManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure one instance across the app."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._keys: List[str] = []
        self._current_index: int = 0
        self._cooldowns: dict[int, float] = {}  # {index: cooldown_until_timestamp}
        self._load_keys()
        self._initialized = True
    
    def _load_keys(self) -> None:
        """Load API keys from GROQ_API_KEYS or GROQ_API_KEY env vars."""
        keys_str = os.getenv("GROQ_API_KEYS", "")
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        
        if not keys:
            # Fallback to single key
            single_key = os.getenv("GROQ_API_KEY", "")
            if single_key:
                keys = [single_key]
        
        if not keys:
            raise ValueError(
                "GROQ_API_KEYS or GROQ_API_KEY must not be empty. "
                "Example: GROQ_API_KEYS=gsk_key1,gsk_key2,gsk_key3"
            )
        
        self._keys = keys
        print(f"[KeyManager] Loaded {len(keys)} API key(s)")
    
    def get_current_key(self) -> str:
        """Get the current active key, skipping keys in cooldown."""
        with self._lock:
            now = time.time()
            attempts = 0
            
            while attempts < len(self._keys):
                cooldown_until = self._cooldowns.get(self._current_index, 0)
                
                if cooldown_until <= now:
                    # Key is available
                    return self._keys[self._current_index]
                
                # Key is in cooldown, try next
                self._rotate_to_next()
                attempts += 1
            
            # All keys in cooldown - return current anyway (will likely fail)
            print(f"[KeyManager] WARNING: All keys in cooldown!")
            return self._keys[self._current_index]
    
    def mark_cooldown(self, retry_after: int = 60) -> None:
        """Mark current key as in cooldown and rotate to next."""
        with self._lock:
            cooldown_until = time.time() + retry_after
            self._cooldowns[self._current_index] = cooldown_until
            key_prefix = self._keys[self._current_index][:10]
            print(f"[KeyManager] Key {key_prefix}... in cooldown for {retry_after}s")
            self._rotate_to_next()
    
    def mark_invalid(self) -> None:
        """Mark current key as permanently invalid (very long cooldown)."""
        with self._lock:
            # Cooldown for 24 hours
            cooldown_until = time.time() + 86400
            self._cooldowns[self._current_index] = cooldown_until
            key_prefix = self._keys[self._current_index][:10]
            print(f"[KeyManager] Key {key_prefix}... marked invalid (24h cooldown)")
            self._rotate_to_next()
    
    def _rotate_to_next(self) -> None:
        """Rotate to the next key in round-robin fashion."""
        self._current_index = (self._current_index + 1) % len(self._keys)
    
    @property
    def key_count(self) -> int:
        """Return the number of loaded keys."""
        return len(self._keys)


# Singleton instance
key_manager = GroqKeyManager()
