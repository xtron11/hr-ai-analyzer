"""
Supabase (PostgreSQL) клиент.

Таблицы:
  - vacancies           — вакансии
  - interviews          — интервью
  - files               — метаданные файлов
  - interview_artifacts — привязка файлов к интервью

Плавная деградация: если SUPABASE_URL / SUPABASE_KEY не заданы,
все методы возвращают None — приложение работает без PostgreSQL.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.config import settings

logger = logging.getLogger("supabase")


class SupabaseClient:
    """Обёртка над supabase-py с graceful degradation."""

    def __init__(self):
        self._client = None
        self._connected: bool = False

    # ── Lifecycle ─────────────────────────────────────────

    async def connect(self):
        """Инициализация Supabase клиента."""
        if not settings.supabase_enabled:
            logger.warning(
                "Supabase URL/KEY не заданы — работаем без PostgreSQL. "
                "Для подключения задайте SUPABASE_URL и SUPABASE_KEY в .env"
            )
            return

        try:
            from supabase import create_client

            self._client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY,
            )
            self._connected = True
            logger.info(f"Supabase подключен: {settings.SUPABASE_URL}")

        except Exception as e:
            logger.error(f"Supabase недоступен: {e}")
            self._connected = False

    async def disconnect(self):
        """Supabase клиент stateless — очистка ссылки."""
        self._client = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Vacancies ─────────────────────────────────────────

    async def create_vacancy(
        self,
        title: str,
        description: Optional[str] = None,
        corporate_values: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Создать вакансию. Возвращает запись или None."""
        if not self._connected:
            return None
        try:
            data = {
                "id": str(uuid4()),
                "title": title,
                "description": description,
                "corporate_values": corporate_values,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            result = self._client.table("vacancies").insert(data).execute()
            logger.info(f"Вакансия создана: {data['id']}")
            return result.data[0] if result.data else data
        except Exception as e:
            logger.error(f"Ошибка создания вакансии: {e}")
            return None

    async def get_vacancy(self, vacancy_id: str) -> Optional[Dict[str, Any]]:
        """Получить вакансию по ID."""
        if not self._connected:
            return None
        try:
            result = (
                self._client.table("vacancies")
                .select("*")
                .eq("id", vacancy_id)
                .single()
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"Ошибка чтения вакансии: {e}")
            return None

    async def get_vacancies(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Получить список вакансий."""
        if not self._connected:
            return []
        try:
            result = (
                self._client.table("vacancies")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Ошибка чтения вакансий: {e}")
            return []

    # ── Interviews ────────────────────────────────────────

    async def create_interview(
        self,
        vacancy_id: str,
        candidate_external_ref: Optional[str] = None,
        status: str = "pending",
    ) -> Optional[Dict[str, Any]]:
        """Создать интервью."""
        if not self._connected:
            return None
        try:
            now = datetime.now(timezone.utc).isoformat()
            data = {
                "id": str(uuid4()),
                "vacancy_id": vacancy_id,
                "candidate_external_ref": candidate_external_ref,
                "status": status,
                "created_at": now,
                "updated_at": now,
            }
            result = self._client.table("interviews").insert(data).execute()
            logger.info(f"Интервью создано: {data['id']}")
            return result.data[0] if result.data else data
        except Exception as e:
            logger.error(f"Ошибка создания интервью: {e}")
            return None

    async def get_interview(self, interview_id: str) -> Optional[Dict[str, Any]]:
        """Получить интервью по ID."""
        if not self._connected:
            return None
        try:
            result = (
                self._client.table("interviews")
                .select("*")
                .eq("id", interview_id)
                .single()
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"Ошибка чтения интервью: {e}")
            return None

    async def update_interview_status(
        self, interview_id: str, status: str
    ) -> Optional[Dict[str, Any]]:
        """Обновить статус интервью."""
        if not self._connected:
            return None
        try:
            result = (
                self._client.table("interviews")
                .update({
                    "status": status,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                .eq("id", interview_id)
                .execute()
            )
            logger.info(f"Статус интервью {interview_id} → {status}")
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Ошибка обновления статуса: {e}")
            return None

    async def get_interviews_by_vacancy(
        self, vacancy_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Получить интервью по вакансии."""
        if not self._connected:
            return []
        try:
            result = (
                self._client.table("interviews")
                .select("*")
                .eq("vacancy_id", vacancy_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Ошибка чтения интервью: {e}")
            return []

    # ── Files ─────────────────────────────────────────────

    async def create_file_record(
        self,
        storage_provider: str,
        storage_key: str,
        original_name: str,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        checksum_sha256: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Создать запись о файле (метаданные)."""
        if not self._connected:
            return None
        try:
            data = {
                "id": str(uuid4()),
                "storage_provider": storage_provider,
                "storage_key": storage_key,
                "original_name": original_name,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "checksum_sha256": checksum_sha256,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            result = self._client.table("files").insert(data).execute()
            logger.info(f"Файл зарегистрирован: {data['id']} ({original_name})")
            return result.data[0] if result.data else data
        except Exception as e:
            logger.error(f"Ошибка создания записи файла: {e}")
            return None

    # ── Interview Artifacts ───────────────────────────────

    async def create_artifact(
        self,
        interview_id: str,
        file_id: str,
        artifact_type: str,
        direction: str = "input",
    ) -> Optional[Dict[str, Any]]:
        """Создать привязку артефакта к интервью."""
        if not self._connected:
            return None
        try:
            data = {
                "id": str(uuid4()),
                "interview_id": interview_id,
                "file_id": file_id,
                "artifact_type": artifact_type,
                "direction": direction,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            result = self._client.table("interview_artifacts").insert(data).execute()
            logger.info(
                f"Артефакт создан: {artifact_type} ({direction}) "
                f"для интервью {interview_id}"
            )
            return result.data[0] if result.data else data
        except Exception as e:
            logger.error(f"Ошибка создания артефакта: {e}")
            return None

    async def get_artifacts_by_interview(
        self, interview_id: str
    ) -> List[Dict[str, Any]]:
        """Получить артефакты интервью."""
        if not self._connected:
            return []
        try:
            result = (
                self._client.table("interview_artifacts")
                .select("*, files(*)")
                .eq("interview_id", interview_id)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Ошибка чтения артефактов: {e}")
            return []


# Глобальный синглтон
supabase_client = SupabaseClient()
