"""
LLM Client Factory
Creates appropriate OpenAI client based on configuration (Azure or direct OpenAI).
"""

from typing import Optional
import os
from openai import AsyncAzureOpenAI, AsyncOpenAI

from app.core.config import Config, get_config


def get_azure_token() -> str:
    """Get Azure token using DefaultAzureCredential."""
    from azure.identity import DefaultAzureCredential
    
    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    return token.token


class AzureTokenProvider:
    """Token provider for Azure OpenAI that refreshes tokens."""
    
    def __init__(self):
        from azure.identity import DefaultAzureCredential
        self.credential = DefaultAzureCredential()
    
    def __call__(self) -> str:
        token = self.credential.get_token("https://cognitiveservices.azure.com/.default")
        return token.token


def create_llm_client(config: Optional[Config] = None) -> AsyncOpenAI | AsyncAzureOpenAI:
    """
    Create an async LLM client based on configuration.
    
    If Azure endpoint is configured, uses Azure OpenAI with DefaultAzureCredential.
    Otherwise, uses direct OpenAI API with the provided API key.
    
    Args:
        config: Configuration object. If None, loads from default config file.
        
    Returns:
        AsyncOpenAI or AsyncAzureOpenAI client instance.
        
    Raises:
        ValueError: If neither Azure nor OpenAI is properly configured.
    """
    if config is None:
        config = get_config()
    
    if config.use_azure:
        # Use Azure OpenAI with API key if provided; otherwise fall back to DefaultAzureCredential.
        api_key = config.azure.api_key.strip() or os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        if api_key:
            return AsyncAzureOpenAI(
                azure_endpoint=config.azure.endpoint,
                api_key=api_key,
                api_version=config.azure.api_version,
            )

        token_provider = AzureTokenProvider()
        return AsyncAzureOpenAI(
            azure_endpoint=config.azure.endpoint,
            azure_ad_token_provider=token_provider,
            api_version=config.azure.api_version,
        )
    elif config.openai.is_configured:
        # Use direct OpenAI API
        kwargs = {
            "api_key": config.openai.api_key,
        }
        if config.openai.base_url:
            kwargs["base_url"] = config.openai.base_url
        
        return AsyncOpenAI(**kwargs)
    else:
        raise ValueError(
            "No LLM configuration found. Please configure either:\n"
            "1. Azure OpenAI: Set [azure].endpoint in config.toml\n"
            "2. OpenAI API: Set [openai].api_key in config.toml"
        )


def get_model_name(config: Optional[Config] = None) -> str:
    """Get the model/deployment name to use for requests."""
    if config is None:
        config = get_config()
    
    if config.use_azure:
        return config.azure.deployment_name
    else:
        return config.openai.model
