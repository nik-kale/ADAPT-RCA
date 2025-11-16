"""
Factory for creating LLM providers.
"""
import logging
from typing import Optional

from .base import LLMProvider

logger = logging.getLogger(__name__)


def get_llm_provider(
    provider_name: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> Optional[LLMProvider]:
    """
    Get an LLM provider instance.

    Args:
        provider_name: Name of the provider ("openai", "anthropic", "none")
        model: Model identifier (provider-specific)
        api_key: API key for the provider
        **kwargs: Additional provider-specific parameters

    Returns:
        LLMProvider instance or None if provider is "none"

    Raises:
        ValueError: If provider name is not recognized
        ImportError: If required package is not installed
    """
    provider_name = provider_name.lower()

    if provider_name == "none" or not provider_name:
        logger.info("LLM provider disabled")
        return None

    if provider_name == "openai":
        from .openai_provider import OpenAIProvider
        model = model or "gpt-4"
        logger.info(f"Using OpenAI provider with model {model}")
        return OpenAIProvider(model=model, api_key=api_key, **kwargs)

    elif provider_name == "anthropic":
        from .anthropic_provider import AnthropicProvider
        model = model or "claude-3-sonnet-20240229"
        logger.info(f"Using Anthropic provider with model {model}")
        return AnthropicProvider(model=model, api_key=api_key, **kwargs)

    else:
        raise ValueError(
            f"Unknown LLM provider: {provider_name}. "
            f"Supported providers: openai, anthropic, none"
        )
