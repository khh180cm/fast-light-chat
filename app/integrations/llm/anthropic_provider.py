"""Anthropic (Claude) LLM provider implementation."""

import logging

from anthropic import AsyncAnthropic

from app.integrations.llm.base import LLMProvider, LLMProviderType, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    provider_type = LLMProviderType.ANTHROPIC

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-haiku-20240307",
        max_tokens: int = 500,
    ):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def transform_message(
        self,
        original_message: str,
        system_prompt: str,
    ) -> LLMResponse:
        """Transform message using Claude."""
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"다음 메시지를 변환해주세요:\n\n{original_message}",
                    },
                ],
            )

            # Extract text from response
            content = original_message
            if response.content and len(response.content) > 0:
                content = response.content[0].text

            return LLMResponse(
                content=content.strip(),
                provider=self.provider_type,
                model=self._model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        except Exception as e:
            logger.error(f"Anthropic transform error: {e}")
            # Return original message on error
            return LLMResponse(
                content=original_message,
                provider=self.provider_type,
                model=self._model,
            )

    async def health_check(self) -> bool:
        """Check Anthropic API availability."""
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return bool(response.content)
        except Exception as e:
            logger.error(f"Anthropic health check failed: {e}")
            return False
