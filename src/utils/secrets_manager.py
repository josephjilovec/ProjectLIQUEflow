"""
Secrets Management Utility
Handles secure retrieval of API keys and configuration from environment variables or Streamlit secrets.
"""

import os
from typing import Optional
import streamlit as st


class SecretsManager:
    """Manages secure access to API keys and sensitive configuration."""
    
    @staticmethod
    def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a secret from Streamlit secrets or environment variables.
        
        Args:
            key: The secret key to retrieve
            default: Default value if secret is not found
            
        Returns:
            The secret value or default
        """
        try:
            # Try Streamlit secrets first (for Streamlit Cloud)
            if hasattr(st, 'secrets') and key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass
        
        # Fallback to environment variables
        return os.getenv(key, default)
    
    @staticmethod
    def get_openai_api_key() -> Optional[str]:
        """Get OpenAI API key."""
        return SecretsManager.get_secret("OPENAI_API_KEY")
    
    @staticmethod
    def get_anthropic_api_key() -> Optional[str]:
        """Get Anthropic API key."""
        return SecretsManager.get_secret("ANTHROPIC_API_KEY")
    
    @staticmethod
    def get_model_provider() -> str:
        """Get the LLM provider preference."""
        return SecretsManager.get_secret("MODEL_PROVIDER", "openai")
    
    @staticmethod
    def get_model_name() -> str:
        """Get the model name."""
        return SecretsManager.get_secret("MODEL_NAME", "gpt-4o")
    
    @staticmethod
    def get_max_allowable_variance() -> float:
        """Get maximum allowable variance for circuit breaker (in USD)."""
        return float(SecretsManager.get_secret("MAX_ALLOWABLE_VARIANCE", "1000000000.0"))  # $1B default
    
    @staticmethod
    def get_max_liquidity_percentage() -> float:
        """Get maximum percentage of total liquidity that can be used in a single transaction."""
        return float(SecretsManager.get_secret("MAX_LIQUIDITY_PERCENTAGE", "0.5"))  # 50% default
