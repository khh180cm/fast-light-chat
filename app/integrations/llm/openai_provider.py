"""OpenAI LLM provider implementation."""

import logging

from openai import AsyncOpenAI

from app.integrations.llm.base import LLMProvider, LLMProviderType, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    provider_type = LLMProviderType.OPENAI

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 500,
    ):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def transform_message(
        self,
        original_message: str,
        system_prompt: str,
    ) -> LLMResponse:
        """Transform message using OpenAI."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"다음 메시지를 변환해주세요:\n\n{original_message}",
                    },
                ],
                max_tokens=self._max_tokens,
                temperature=0.7,
            )

            content = response.choices[0].message.content or original_message
            usage = response.usage

            return LLMResponse(
                content=content.strip(),
                provider=self.provider_type,
                model=self._model,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
            )

        except Exception as e:
            logger.error(f"OpenAI transform error: {e}")
            # Return original message on error
            return LLMResponse(
                content=original_message,
                provider=self.provider_type,
                model=self._model,
            )

    async def health_check(self) -> bool:
        """Check OpenAI API availability."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return bool(response.choices)
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False
