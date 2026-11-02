"""
Pydantic-модели для PostgreSQL (Supabase) таблиц.
Соответствуют схеме: vacancies, interviews, files, interview_artifacts.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.enums import (
    ArtifactDirection,
    ArtifactType,
    InterviewStatus,
    StorageProvider,
)


# ═══════════════════════════════════════════════════════════
#  vacancies
# ═══════════════════════════════════════════════════════════

class VacancyCreate(BaseModel):
    """Создание новой вакансии."""
    title: str = Field(..., max_length=255, description="Название вакансии")
    description: Optional[str] = Field(None, description="Описание вакансии (вход #1)")
    corporate_values: Optional[str] = Field(None, description="Корпоративные ценности (вход #2)")


class Vacancy(VacancyCreate):
    """Вакансия из БД."""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════
#  interviews
# ═══════════════════════════════════════════════════════════

class InterviewCreate(BaseModel):
    """Создание нового интервью."""
    vacancy_id: UUID = Field(..., description="FK → vacancies.id")
    candidate_external_ref: Optional[str] = Field(None, description="Внешний ID кандидата")
    status: InterviewStatus = Field(default=InterviewStatus.PENDING)


class Interview(InterviewCreate):
    """Интервью из БД."""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════
#  files (метаданные, сам файл в Object Storage)
# ═══════════════════════════════════════════════════════════

class FileRecordCreate(BaseModel):
    """Создание записи о файле."""
    storage_provider: StorageProvider = Field(..., description="Провайдер хранения")
    storage_key: str = Field(..., description="Ключ / путь в storage")
    original_name: str = Field(..., description="Оригинальное имя файла")
    mime_type: Optional[str] = Field(None, max_length=100)
    size_bytes: Optional[int] = Field(None, ge=0)
    checksum_sha256: Optional[str] = Field(None, max_length=64)


class FileRecord(FileRecordCreate):
    """Файл из БД."""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════
#  interview_artifacts (привязка файлов к интервью)
# ═══════════════════════════════════════════════════════════

class InterviewArtifactCreate(BaseModel):
    """Создание привязки артефакта к интервью."""
    interview_id: UUID = Field(..., description="FK → interviews.id")
    file_id: UUID = Field(..., description="FK → files.id")
    artifact_type: ArtifactType = Field(..., description="Тип артефакта")
    direction: ArtifactDirection = Field(..., description="Направление: input/output")


class InterviewArtifact(InterviewArtifactCreate):
    """Артефакт интервью из БД."""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
