"""LLM provider factory."""

from app.core.config import settings
from app.integrations.llm.base import LLMProvider, LLMProviderType


def get_llm_provider(
    provider_type: LLMProviderType | str | None = None,
) -> LLMProvider:
    """
    Get LLM provider instance based on configuration.

    Args:
        provider_type: Provider type to use. If None, uses config settings.

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider is not configured or invalid
    """
    # Determine provider type
    if provider_type is None:
        provider_type = settings.llm_provider

    if isinstance(provider_type, str):
        provider_type = LLMProviderType(provider_type.lower())

    if provider_type == LLMProviderType.OPENAI:
        from app.integrations.llm.openai_provider import OpenAIProvider

        api_key = settings.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        return OpenAIProvider(api_key=api_key, model=settings.openai_model)

    elif provider_type == LLMProviderType.ANTHROPIC:
        from app.integrations.llm.anthropic_provider import AnthropicProvider

        api_key = settings.anthropic_api_key
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        return AnthropicProvider(api_key=api_key, model=settings.anthropic_model)

    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")


def get_available_providers() -> list[LLMProviderType]:
    """Get list of available (configured) LLM providers."""
    available = []

    if settings.openai_api_key:
        available.append(LLMProviderType.OPENAI)

    if settings.anthropic_api_key:
        available.append(LLMProviderType.ANTHROPIC)

    return available
