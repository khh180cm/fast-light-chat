"""Satisfaction survey repository for MongoDB."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domains.satisfaction.models import SatisfactionSurvey, SurveyStatus


class SatisfactionRepositoryInterface(ABC):
    """Abstract repository interface for satisfaction surveys."""

    @abstractmethod
    async def create(self, survey: SatisfactionSurvey) -> SatisfactionSurvey:
        """Create a new survey."""
        pass

    @abstractmethod
    async def get_by_id(self, survey_id: str) -> SatisfactionSurvey | None:
        """Get survey by ID."""
        pass

    @abstractmethod
    async def get_by_chat_id(self, chat_id: str) -> SatisfactionSurvey | None:
        """Get survey by chat ID."""
        pass

    @abstractmethod
    async def submit_response(
        self,
        survey_id: str,
        rating: int,
        feedback: str | None,
    ) -> bool:
        """Submit survey response."""
        pass

    @abstractmethod
    async def mark_skipped(self, survey_id: str) -> bool:
        """Mark survey as skipped."""
        pass

    @abstractmethod
    async def get_statistics(self) -> dict:
        """Get survey statistics."""
        pass


class MongoSatisfactionRepository(SatisfactionRepositoryInterface):
    """MongoDB implementation of satisfaction repository."""

    def __init__(self, db: AsyncIOMotorDatabase, org_id: str, env_type: str):
        self._db = db
        self._org_id = org_id
        self._env_type = env_type
        self._collection = db[f"satisfaction_surveys_{org_id}_{env_type}"]

    async def create(self, survey: SatisfactionSurvey) -> SatisfactionSurvey:
        """Create a new satisfaction survey."""
        doc = survey.model_dump(by_alias=True, exclude={"id"})
        result = await self._collection.insert_one(doc)
        survey.id = str(result.inserted_id)
        return survey

    async def get_by_id(self, survey_id: str) -> SatisfactionSurvey | None:
        """Get survey by ID."""
        doc = await self._collection.find_one({"_id": ObjectId(survey_id)})
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        return SatisfactionSurvey(**doc)

    async def get_by_chat_id(self, chat_id: str) -> SatisfactionSurvey | None:
        """Get survey by chat ID."""
        doc = await self._collection.find_one({"chat_id": chat_id})
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        return SatisfactionSurvey(**doc)

    async def submit_response(
        self,
        survey_id: str,
        rating: int,
        feedback: str | None,
    ) -> bool:
        """Submit survey response."""
        result = await self._collection.update_one(
            {
                "_id": ObjectId(survey_id),
                "status": SurveyStatus.PENDING,
            },
            {
                "$set": {
                    "rating": rating,
                    "feedback": feedback,
                    "status": SurveyStatus.COMPLETED,
                    "responded_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0

    async def mark_skipped(self, survey_id: str) -> bool:
        """Mark survey as skipped."""
        result = await self._collection.update_one(
            {
                "_id": ObjectId(survey_id),
                "status": SurveyStatus.PENDING,
            },
            {
                "$set": {
                    "status": SurveyStatus.SKIPPED,
                    "responded_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0

    async def list_surveys(
        self,
        status: SurveyStatus | None = None,
        agent_id: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[SatisfactionSurvey], str | None, bool]:
        """List surveys with pagination."""
        query: dict = {}

        if status:
            query["status"] = status
        if agent_id:
            query["agent_id"] = agent_id
        if cursor:
            query["_id"] = {"$lt": ObjectId(cursor)}

        cursor_result = self._collection.find(query).sort("_id", -1).limit(limit + 1)
        docs = await cursor_result.to_list(length=limit + 1)

        has_more = len(docs) > limit
        if has_more:
            docs = docs[:limit]

        surveys = []
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            surveys.append(SatisfactionSurvey(**doc))

        next_cursor = surveys[-1].id if has_more and surveys else None
        return surveys, next_cursor, has_more

    async def get_statistics(self) -> dict:
        """Get satisfaction survey statistics."""
        pipeline = [
            {
                "$facet": {
                    "status_counts": [
                        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
                    ],
                    "rating_stats": [
                        {"$match": {"status": SurveyStatus.COMPLETED, "rating": {"$ne": None}}},
                        {
                            "$group": {
                                "_id": None,
                                "avg_rating": {"$avg": "$rating"},
                                "total": {"$sum": 1},
                            }
                        },
                    ],
                    "rating_distribution": [
                        {"$match": {"status": SurveyStatus.COMPLETED, "rating": {"$ne": None}}},
                        {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
                    ],
                }
            }
        ]

        result = await self._collection.aggregate(pipeline).to_list(length=1)

        if not result:
            return {
                "total_surveys": 0,
                "completed_surveys": 0,
                "skipped_surveys": 0,
                "expired_surveys": 0,
                "average_rating": None,
                "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                "response_rate": 0.0,
            }

        data = result[0]

        # Parse status counts
        status_map = {item["_id"]: item["count"] for item in data["status_counts"]}
        completed = status_map.get(SurveyStatus.COMPLETED, 0)
        skipped = status_map.get(SurveyStatus.SKIPPED, 0)
        expired = status_map.get(SurveyStatus.EXPIRED, 0)
        pending = status_map.get(SurveyStatus.PENDING, 0)
        total = completed + skipped + expired + pending

        # Parse rating stats
        avg_rating = None
        if data["rating_stats"]:
            avg_rating = data["rating_stats"][0].get("avg_rating")

        # Parse rating distribution
        rating_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for item in data["rating_distribution"]:
            if item["_id"] in rating_dist:
                rating_dist[item["_id"]] = item["count"]

        # Calculate response rate
        denominator = completed + skipped + expired
        response_rate = (completed / denominator * 100) if denominator > 0 else 0.0

        return {
            "total_surveys": total,
            "completed_surveys": completed,
            "skipped_surveys": skipped,
            "expired_surveys": expired,
            "average_rating": round(avg_rating, 2) if avg_rating else None,
            "rating_distribution": rating_dist,
            "response_rate": round(response_rate, 2),
        }
