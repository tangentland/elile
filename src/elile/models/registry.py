"""Model registry and factory for creating model adapters."""

from functools import lru_cache

from elile.config.settings import ModelProvider, get_settings
from elile.models.anthropic_adapter import AnthropicAdapter
from elile.models.base import BaseModelAdapter
from elile.models.gemini_adapter import GeminiAdapter
from elile.models.openai_adapter import OpenAIAdapter
from elile.utils.exceptions import ConfigurationError


@lru_cache
def get_model(provider: ModelProvider | None = None) -> BaseModelAdapter:
    """Get a model adapter for the specified provider.

    Args:
        provider: The model provider to use. If None, uses the default from settings.

    Returns:
        A configured model adapter.

    Raises:
        ConfigurationError: If the API key for the provider is not configured.
    """
    settings = get_settings()

    if provider is None:
        provider = settings.default_model_provider

    api_key = settings.get_api_key(provider)
    if api_key is None:
        raise ConfigurationError(f"API key not configured for provider: {provider.value}")

    model_name = settings.get_model_name(provider)

    match provider:
        case ModelProvider.ANTHROPIC:
            return AnthropicAdapter(api_key=api_key, model=model_name)
        case ModelProvider.OPENAI:
            return OpenAIAdapter(api_key=api_key, model=model_name)
        case ModelProvider.GOOGLE:
            return GeminiAdapter(api_key=api_key, model=model_name)
