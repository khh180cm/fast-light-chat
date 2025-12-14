"""Satisfaction survey service - business logic."""

from datetime import datetime, timedelta, timezone

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.satisfaction.models import SatisfactionSurvey, SurveyStatus
from app.domains.satisfaction.repository import SatisfactionRepositoryInterface
from app.domains.satisfaction.schemas import SatisfactionCreate, SatisfactionStatistics


class SatisfactionService:
    """Satisfaction survey management service."""

    def __init__(
        self,
        repository: SatisfactionRepositoryInterface,
        org_id: str,
        env_type: str,
    ):
        self._repo = repository
        self._org_id = org_id
        self._env_type = env_type

    async def create_survey(
        self,
        chat_id: str,
        user_id: str,
        member_id: str,
        triggered_by: str,
        agent_id: str | None = None,
        expires_in_hours: int = 72,
    ) -> SatisfactionSurvey:
        """
        Create a satisfaction survey for a chat.

        Args:
            chat_id: Chat ID
            user_id: User's MongoDB ID
            member_id: User's external member ID
            triggered_by: What triggered the survey (agent_resolve, user_close, auto_close)
            agent_id: Agent who handled the chat
            expires_in_hours: Hours until survey expires

        Returns:
            Created survey
        """
        # Check if survey already exists for this chat
        existing = await self._repo.get_by_chat_id(chat_id)
        if existing:
            return existing

        survey = SatisfactionSurvey(
            org_id=self._org_id,
            env_type=self._env_type,
            chat_id=chat_id,
            user_id=user_id,
            member_id=member_id,
            agent_id=agent_id,
            triggered_by=triggered_by,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
        )

        return await self._repo.create(survey)

    async def get_survey(self, survey_id: str) -> SatisfactionSurvey:
        """Get survey by ID."""
        survey = await self._repo.get_by_id(survey_id)
        if not survey:
            raise NotFoundError("Survey", survey_id)
        return survey

    async def get_survey_by_chat(self, chat_id: str) -> SatisfactionSurvey | None:
        """Get survey by chat ID."""
        return await self._repo.get_by_chat_id(chat_id)

    async def submit_response(
        self,
        survey_id: str,
        data: SatisfactionCreate,
    ) -> SatisfactionSurvey:
        """
        Submit survey response.

        Args:
            survey_id: Survey ID
            data: Survey response data

        Returns:
            Updated survey
        """
        survey = await self.get_survey(survey_id)

        if survey.status != SurveyStatus.PENDING:
            raise ValidationError(f"Survey is already {survey.status}")

        # Check if expired
        if survey.expires_at and datetime.now(timezone.utc) > survey.expires_at:
            raise ValidationError("Survey has expired")

        success = await self._repo.submit_response(
            survey_id=survey_id,
            rating=data.rating,
            feedback=data.feedback,
        )

        if not success:
            raise ValidationError("Failed to submit survey response")

        return await self.get_survey(survey_id)

    async def skip_survey(self, survey_id: str) -> SatisfactionSurvey:
        """Mark survey as skipped."""
        survey = await self.get_survey(survey_id)

        if survey.status != SurveyStatus.PENDING:
            raise ValidationError(f"Survey is already {survey.status}")

        await self._repo.mark_skipped(survey_id)
        return await self.get_survey(survey_id)

    async def get_statistics(self) -> SatisfactionStatistics:
        """Get satisfaction survey statistics."""
        stats = await self._repo.get_statistics()
        return SatisfactionStatistics(**stats)
