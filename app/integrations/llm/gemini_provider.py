"""Google Gemini LLM provider implementation."""

import logging

from google import genai
from google.genai import types

from app.integrations.llm.base import LLMProvider, LLMProviderType, LLMResponse

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    provider_type = LLMProviderType.GEMINI

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 500,
    ):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def transform_message(
        self,
        original_message: str,
        system_prompt: str,
    ) -> LLMResponse:
        """Transform message using Gemini."""
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=f"다음 메시지를 변환해주세요:\n\n{original_message}",
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=self._max_tokens,
                    temperature=0.7,
                ),
            )

            content = response.text or original_message

            # Token usage
            input_tokens = 0
            output_tokens = 0
            if response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0

            return LLMResponse(
                content=content.strip(),
                provider=self.provider_type,
                model=self._model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        except Exception as e:
            logger.error(f"Gemini transform error: {e}")
            return LLMResponse(
                content=original_message,
                provider=self.provider_type,
                model=self._model,
            )

    async def health_check(self) -> bool:
        """Check Gemini API availability."""
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=10),
            )
            return bool(response.text)
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return False
