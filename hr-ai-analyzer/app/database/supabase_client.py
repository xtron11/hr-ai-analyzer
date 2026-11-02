"""
Supabase клиент для hr-ai-analyzer.
Обновляет статус интервью и создаёт выходные артефакты.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from app.config import settings

logger = logging.getLogger("hr.supabase")


class SupabaseClient:
    def __init__(self):
        self._client = None
        self._connected: bool = False

    async def connect(self):
        if not settings.supabase_enabled:
            logger.warning("Supabase URL/KEY не заданы — без PostgreSQL")
            return
        try:
            from supabase import create_client
            self._client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            self._connected = True
            logger.info(f"Supabase подключен: {settings.SUPABASE_URL}")
        except Exception as e:
            logger.error(f"Supabase недоступен: {e}")
            self._connected = False

    async def disconnect(self):
        self._client = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def update_interview_status(self, interview_id: str, status: str) -> Optional[Dict]:
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
            logger.info(f"Интервью {interview_id} → {status}")
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Ошибка обновления статуса: {e}")
            return None

    async def create_artifact(
        self,
        interview_id: str,
        file_id: str,
        artifact_type: str,
        direction: str = "output",
    ) -> Optional[Dict]:
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
            logger.info(f"Артефакт создан: {artifact_type} для {interview_id}")
            return result.data[0] if result.data else data
        except Exception as e:
            logger.error(f"Ошибка создания артефакта: {e}")
            return None

    async def create_file_record(
        self,
        storage_provider: str,
        storage_key: str,
        original_name: str,
        mime_type: Optional[str] = "application/json",
        size_bytes: Optional[int] = None,
        checksum_sha256: Optional[str] = None,
    ) -> Optional[Dict]:
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
            logger.info(f"Файл зарегистрирован: {original_name}")
            return result.data[0] if result.data else data
        except Exception as e:
            logger.error(f"Ошибка создания записи файла: {e}")
            return None


supabase_client = SupabaseClient()
