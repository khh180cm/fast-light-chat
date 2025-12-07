"""Message transformer using LLM."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.tone_profile.service import ToneProfileService
from app.integrations.llm.base import LLMProvider, LLMProviderType, LLMResponse
from app.integrations.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)


class MessageTransformer:
    """
    Transforms agent messages using AI based on organization's tone profile.

    This is the main interface for the message transformation feature.
    """

    def __init__(
        self,
        session: AsyncSession,
        org_id: UUID,
        provider: LLMProvider | None = None,
    ):
        self._session = session
        self._org_id = org_id
        self._tone_service = ToneProfileService(session, org_id)

        # Use provided provider or get default
        self._provider = provider

    async def _get_provider(self) -> LLMProvider:
        """Get LLM provider, lazy initialization."""
        if self._provider is None:
            self._provider = get_llm_provider()
        return self._provider

    async def transform(
        self,
        original_message: str,
        provider_type: LLMProviderType | None = None,
    ) -> dict:
        """
        Transform a message using the organization's tone profile.

        Args:
            original_message: The original message to transform
            provider_type: Optional specific provider to use

        Returns:
            Dict with original, transformed message, and metadata
        """
        # Get tone profile
        profile = await self._tone_service.get_or_create_profile()

        # Check if profile is active
        if not profile.is_active:
            return {
                "original_message": original_message,
                "transformed_message": original_message,
                "tone_profile_name": profile.name,
                "tone_profile_version": profile.current_version,
                "transformation_skipped": True,
                "skip_reason": "Tone profile is disabled",
            }

        # Get provider
        if provider_type:
            provider = get_llm_provider(provider_type)
        else:
            provider = await self._get_provider()

        # Transform message
        response = await provider.transform_message(
            original_message=original_message,
            system_prompt=profile.prompt,
        )

        return {
            "original_message": original_message,
            "transformed_message": response.content,
            "tone_profile_name": profile.name,
            "tone_profile_version": profile.current_version,
            "provider": response.provider.value,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }

    async def preview_transform(
        self,
        original_message: str,
        custom_prompt: str | None = None,
        provider_type: LLMProviderType | None = None,
    ) -> dict:
        """
        Preview transformation with optional custom prompt.

        Useful for testing new prompts before saving.

        Args:
            original_message: Message to transform
            custom_prompt: Custom prompt to use instead of saved profile
            provider_type: Optional specific provider to use

        Returns:
            Dict with transformation result
        """
        # Get prompt
        if custom_prompt:
            prompt = custom_prompt
            profile_name = "(preview)"
            profile_version = 0
        else:
            profile = await self._tone_service.get_or_create_profile()
            prompt = profile.prompt
            profile_name = profile.name
            profile_version = profile.current_version

        # Get provider
        if provider_type:
            provider = get_llm_provider(provider_type)
        else:
            provider = await self._get_provider()

        # Transform
        response = await provider.transform_message(
            original_message=original_message,
            system_prompt=prompt,
        )

        return {
            "original_message": original_message,
            "transformed_message": response.content,
            "tone_profile_name": profile_name,
            "tone_profile_version": profile_version,
            "provider": response.provider.value,
            "model": response.model,
            "is_preview": True,
        }
