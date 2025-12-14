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

    if provider_type == LLMProviderType.GEMINI:
        from app.integrations.llm.gemini_provider import GeminiProvider

        api_key = settings.gemini_api_key
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        return GeminiProvider(api_key=api_key, model=settings.gemini_model)

    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")


def get_available_providers() -> list[LLMProviderType]:
    """Get list of available (configured) LLM providers."""
    available = []

    if settings.gemini_api_key:
        available.append(LLMProviderType.GEMINI)

    return available
