"""
Enum'ы по схеме базы данных.
Используются в Pydantic-моделях и при валидации данных.
"""

from enum import Enum


class ArtifactType(str, Enum):
    """Тип артефакта интервью."""
    COVER_LETTER = "cover_letter"
    RESUME = "resume"
    TEST_TASK_RESULT = "test_task_result"
    TRANSCRIPT_TEXT = "transcript_text"
    AUDIO_RECORDING = "audio_recording"
    VIDEO_FRAMES = "video_frames"
    AUDITOR_COMMENT = "auditor_comment"
    OTHER = "other"


class ArtifactDirection(str, Enum):
    """Направление артефакта: входные данные или результат обработки."""
    INPUT = "input"
    OUTPUT = "output"


class StorageProvider(str, Enum):
    """Провайдер хранения файлов."""
    S3 = "s3"
    MINIO = "minio"
    LOCAL_DEV = "local_dev"


class InterviewStatus(str, Enum):
    """Статус интервью в pipeline."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AUDIO_ANALYZING = "audio_analyzing"
    TEXT_ANALYZING = "text_analyzing"
    VIDEO_ANALYZING = "video_analyzing"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"
