"""
MongoDB клиент (Motor — async driver).

Коллекции:
  - audio_analysis   — результаты аудио-анализа
  - text_analysis     — результаты текстового анализа (заглушка)
  - video_analysis    — результаты видео-анализа (заглушка)
  - aggregated_reports — финальные отчёты

Индексы создаются при старте приложения.
Плавная деградация: если MongoDB недоступна, методы возвращают None / пустые значения.
"""

import logging
from typing import Any, Dict, List, Optional

import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

logger = logging.getLogger("mongodb")


class MongoDBClient:
    """Обёртка над Motor с graceful degradation."""

    def __init__(self):
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._connected: bool = False

    # ── Lifecycle ─────────────────────────────────────────

    async def connect(self):
        """Подключение к MongoDB. Не бросает исключений — плавная деградация."""
        if not settings.mongo_enabled:
            logger.warning("MongoDB URI не задан, работаем без MongoDB")
            return

        try:
            self._client = AsyncIOMotorClient(
                settings.MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                tlsCAFile=certifi.where(),
            )
            # Проверяем соединение
            await self._client.admin.command("ping")
            self._db = self._client[settings.MONGO_DB_NAME]
            self._connected = True
            logger.info(f"MongoDB подключен: {settings.MONGO_DB_NAME}")

            # Создаём индексы
            await self._ensure_indexes()

        except Exception as e:
            logger.error(f"MongoDB недоступен, продолжаем без него: {e}")
            self._connected = False

    async def disconnect(self):
        """Закрытие соединения."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info("MongoDB отключен")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Indexes ───────────────────────────────────────────

    async def _ensure_indexes(self):
        """Создание индексов по схеме для быстрого поиска по interview_id."""
        if self._db is None:
            return

        try:
            # audio_analysis: { interview_id: 1 }
            await self._db.audio_analysis.create_index(
                [("interview_id", 1)],
                name="idx_interview_id",
                unique=False,
            )

            # text_analysis: { interview_id: 1 }
            await self._db.text_analysis.create_index(
                [("interview_id", 1)],
                name="idx_interview_id",
                unique=False,
            )

            # video_analysis: { interview_id: 1 }
            await self._db.video_analysis.create_index(
                [("interview_id", 1)],
                name="idx_interview_id",
                unique=False,
            )

            # aggregated_reports: { interview_id: 1 }, { generated_at: -1 }
            await self._db.aggregated_reports.create_index(
                [("interview_id", 1)],
                name="idx_interview_id",
                unique=False,
            )
            await self._db.aggregated_reports.create_index(
                [("generated_at", -1)],
                name="idx_generated_at_desc",
            )

            logger.info("MongoDB индексы созданы / подтверждены")

        except Exception as e:
            logger.error(f"Ошибка создания индексов: {e}")

    # ── Collections ───────────────────────────────────────

    @property
    def audio_analysis(self):
        return self._db.audio_analysis if self._db is not None else None

    @property
    def text_analysis(self):
        return self._db.text_analysis if self._db is not None else None

    @property
    def video_analysis(self):
        return self._db.video_analysis if self._db is not None else None

    @property
    def aggregated_reports(self):
        return self._db.aggregated_reports if self._db is not None else None

    # ── CRUD: audio_analysis ──────────────────────────────

    async def insert_audio_analysis(self, document: dict) -> Optional[str]:
        """Сохранить результат аудио-анализа. Возвращает inserted_id или None."""
        if not self._connected or self.audio_analysis is None:
            logger.warning("MongoDB не подключен, audio_analysis не сохранён")
            return None
        try:
            result = await self.audio_analysis.insert_one({**document})
            logger.info(f"audio_analysis сохранён: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Ошибка сохранения audio_analysis: {e}")
            return None

    async def get_audio_analysis(self, interview_id: str) -> Optional[dict]:
        """Получить результат аудио-анализа по interview_id."""
        if not self._connected or self.audio_analysis is None:
            return None
        try:
            doc = await self.audio_analysis.find_one(
                {"interview_id": interview_id},
                sort=[("created_at", -1)],
            )
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            logger.error(f"Ошибка чтения audio_analysis: {e}")
            return None

    # ── CRUD: text_analysis ───────────────────────────────

    async def insert_text_analysis(self, document: dict) -> Optional[str]:
        """Сохранить результат текстового анализа."""
        if not self._connected or self.text_analysis is None:
            return None
        try:
            result = await self.text_analysis.insert_one({**document})
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Ошибка сохранения text_analysis: {e}")
            return None

    async def get_text_analysis(self, interview_id: str) -> Optional[dict]:
        """Получить результат текстового анализа по interview_id."""
        if not self._connected or self.text_analysis is None:
            return None
        try:
            doc = await self.text_analysis.find_one(
                {"interview_id": interview_id},
                sort=[("created_at", -1)],
            )
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            logger.error(f"Ошибка чтения text_analysis: {e}")
            return None

    # ── CRUD: video_analysis ──────────────────────────────

    async def insert_video_analysis(self, document: dict) -> Optional[str]:
        """Сохранить результат видео-анализа."""
        if not self._connected or self.video_analysis is None:
            return None
        try:
            result = await self.video_analysis.insert_one({**document})
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Ошибка сохранения video_analysis: {e}")
            return None

    async def get_video_analysis(self, interview_id: str) -> Optional[dict]:
        """Получить результат видео-анализа по interview_id."""
        if not self._connected or self.video_analysis is None:
            return None
        try:
            doc = await self.video_analysis.find_one(
                {"interview_id": interview_id},
                sort=[("created_at", -1)],
            )
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            logger.error(f"Ошибка чтения video_analysis: {e}")
            return None

    # ── CRUD: aggregated_reports ──────────────────────────

    async def insert_aggregated_report(self, document: dict) -> Optional[str]:
        """Сохранить агрегированный отчёт."""
        if not self._connected or self.aggregated_reports is None:
            return None
        try:
            result = await self.aggregated_reports.insert_one({**document})
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Ошибка сохранения aggregated_report: {e}")
            return None

    async def get_aggregated_report(self, interview_id: str) -> Optional[dict]:
        """Получить последний агрегированный отчёт по interview_id."""
        if not self._connected or self.aggregated_reports is None:
            return None
        try:
            doc = await self.aggregated_reports.find_one(
                {"interview_id": interview_id},
                sort=[("generated_at", -1)],
            )
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            logger.error(f"Ошибка чтения aggregated_report: {e}")
            return None

    async def get_all_reports(self, limit: int = 50) -> List[dict]:
        """Получить список последних отчётов."""
        if not self._connected or self.aggregated_reports is None:
            return []
        try:
            cursor = self.aggregated_reports.find().sort("generated_at", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            for doc in docs:
                doc["_id"] = str(doc["_id"])
            return docs
        except Exception as e:
            logger.error(f"Ошибка чтения reports: {e}")
            return []


# Глобальный синглтон
mongodb = MongoDBClient()
