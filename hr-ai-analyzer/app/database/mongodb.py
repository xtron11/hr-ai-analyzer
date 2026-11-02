"""
MongoDB клиент для hr-ai-analyzer.
Коллекции: text_analysis, aggregated_reports.
"""
import logging
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

logger = logging.getLogger("hr.mongodb")


class MongoDBClient:
    def __init__(self):
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._connected: bool = False

    async def connect(self):
        if not settings.mongo_enabled:
            logger.warning("MongoDB URI не задан")
            return
        try:
            self._client = AsyncIOMotorClient(
                settings.MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
            await self._client.admin.command("ping")
            self._db = self._client[settings.MONGO_DB_NAME]
            self._connected = True
            logger.info(f"MongoDB подключен: {settings.MONGO_DB_NAME}")
            await self._ensure_indexes()
        except Exception as e:
            logger.error(f"MongoDB недоступен: {e}")
            self._connected = False

    async def disconnect(self):
        if self._client:
            self._client.close()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def _ensure_indexes(self):
        if not self._db:
            return
        try:
            await self._db.text_analysis.create_index([("interview_id", 1)], name="idx_interview_id")
            await self._db.aggregated_reports.create_index([("interview_id", 1)], name="idx_interview_id")
            await self._db.aggregated_reports.create_index([("generated_at", -1)], name="idx_generated_at_desc")
            logger.info("MongoDB индексы созданы")
        except Exception as e:
            logger.error(f"Ошибка создания индексов: {e}")

    # ── text_analysis ────────────────────────────────────

    async def insert_text_analysis(self, document: dict) -> Optional[str]:
        if not self._connected or not self._db:
            return None
        try:
            result = await self._db.text_analysis.insert_one(document)
            logger.info(f"text_analysis сохранён: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Ошибка сохранения text_analysis: {e}")
            return None

    async def get_text_analysis(self, interview_id: str) -> Optional[dict]:
        if not self._connected or not self._db:
            return None
        try:
            doc = await self._db.text_analysis.find_one(
                {"interview_id": interview_id}, sort=[("created_at", -1)]
            )
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            logger.error(f"Ошибка чтения text_analysis: {e}")
            return None

    # ── aggregated_reports ───────────────────────────────

    async def insert_aggregated_report(self, document: dict) -> Optional[str]:
        if not self._connected or not self._db:
            return None
        try:
            # Upsert: одна запись на interview
            result = await self._db.aggregated_reports.replace_one(
                {"interview_id": document["interview_id"]},
                document,
                upsert=True,
            )
            logger.info(f"aggregated_report сохранён для {document['interview_id']}")
            return document["interview_id"]
        except Exception as e:
            logger.error(f"Ошибка сохранения aggregated_report: {e}")
            return None

    async def get_aggregated_report(self, interview_id: str) -> Optional[dict]:
        if not self._connected or not self._db:
            return None
        try:
            doc = await self._db.aggregated_reports.find_one(
                {"interview_id": interview_id}, sort=[("generated_at", -1)]
            )
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            logger.error(f"Ошибка чтения aggregated_report: {e}")
            return None

    async def get_all_reports(self, limit: int = 50) -> List[dict]:
        if not self._connected or not self._db:
            return []
        try:
            cursor = self._db.aggregated_reports.find().sort("generated_at", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            for doc in docs:
                doc["_id"] = str(doc["_id"])
            return docs
        except Exception as e:
            logger.error(f"Ошибка чтения reports: {e}")
            return []


mongodb = MongoDBClient()
