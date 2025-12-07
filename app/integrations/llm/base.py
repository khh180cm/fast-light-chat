"""Base LLM provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class LLMProviderType(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class LLMResponse:
    """Response from LLM provider."""

    content: str
    provider: LLMProviderType
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    provider_type: LLMProviderType

    @abstractmethod
    async def transform_message(
        self,
        original_message: str,
        system_prompt: str,
    ) -> LLMResponse:
        """
        Transform a message using the LLM.

        Args:
            original_message: The original message to transform
            system_prompt: Instructions for how to transform the message

        Returns:
            LLMResponse with transformed message
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        pass
