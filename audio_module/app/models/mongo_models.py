"""
Pydantic-модели для MongoDB коллекций.
Соответствуют схеме: audio_analysis, text_analysis, video_analysis, aggregated_reports.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
#  audio_analysis
# ═══════════════════════════════════════════════════════════

class SpeechRateData(BaseModel):
    """Данные о скорости речи."""
    speech_rate_wpm: float = 0.0
    speech_rate_method: str = "asr_words"
    word_count: int = 0
    duration_sec: float = 0.0


class PauseMetrics(BaseModel):
    """Метрики пауз в речи."""
    total_pauses: int = 0
    total_pause_time_sec: float = 0.0
    avg_pause_duration_sec: float = 0.0
    long_pauses_count: int = 0
    pause_rate_per_min: float = 0.0
    pause_threshold_sec: float = 1.5


class PitchMetrics(BaseModel):
    """Метрики основного тона голоса."""
    avg_pitch: float = 0.0
    min_pitch: float = 0.0
    max_pitch: float = 0.0
    std_pitch: float = 0.0
    pitch_range: float = 0.0
    voiced_ratio: float = 0.0


class EmotionTimelineEntry(BaseModel):
    """Запись временной шкалы эмоций."""
    start_sec: float
    end_sec: float
    emotion: str
    confidence: float
    scores: Optional[Dict[str, float]] = None


class EmotionsRecognition(BaseModel):
    """Результаты распознавания эмоций."""
    emotion: str = "neutral"
    confidence: float = 0.0
    emotions_timeline: List[EmotionTimelineEntry] = []


class AudioAnalysisDocument(BaseModel):
    """
    Документ коллекции audio_analysis в MongoDB.
    Содержит полный результат аудио-анализа интервью.
    """
    interview_id: str = Field(..., description="UUID интервью")
    speech_rate: SpeechRateData = Field(default_factory=SpeechRateData)
    pause_metrics: Dict[str, Any] = Field(default_factory=dict)
    pitch_metrics: Dict[str, Any] = Field(default_factory=dict)
    affect_dimensions: Dict[str, Any] = Field(default_factory=dict)
    acoustic_features: Dict[str, Any] = Field(default_factory=dict)
    emotions_recognition: Dict[str, Any] = Field(default_factory=dict)
    complex_emotions: Dict[str, Any] = Field(default_factory=dict)
    transcript_segments: List[Dict[str, Any]] = Field(default_factory=list)
    detected_language: str = "unknown"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ═══════════════════════════════════════════════════════════
#  text_analysis (заглушка — модуль будет реализован позднее)
# ═══════════════════════════════════════════════════════════

class TextAnalysisDocument(BaseModel):
    """
    Документ коллекции text_analysis в MongoDB.
    Анализ текстовых данных: резюме, транскрипции, сопроводительных писем.
    """
    interview_id: str = Field(..., description="UUID интервью")
    source: str = Field(..., description="Источник: resume / transcript / cover_letter")
    skills: List[str] = Field(default_factory=list)
    keyword_scores: Dict[str, Any] = Field(default_factory=dict)
    psych_traits: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════
#  video_analysis (заглушка — модуль будет реализован позднее)
# ═══════════════════════════════════════════════════════════

class VideoAnalysisDocument(BaseModel):
    """
    Документ коллекции video_analysis в MongoDB.
    Анализ видеоданных: мимика, взгляд, жесты.
    """
    interview_id: str = Field(..., description="UUID интервью")
    facial: Dict[str, Any] = Field(default_factory=dict, description="Мимический анализ")
    gaze: Dict[str, Any] = Field(default_factory=dict, description="Контакт глаз (eye contact)")
    pose_gesture: Dict[str, Any] = Field(default_factory=dict, description="Поза и жесты")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════
#  aggregated_reports
# ═══════════════════════════════════════════════════════════

class AggregatedReportDocument(BaseModel):
    """
    Документ коллекции aggregated_reports в MongoDB.
    Финальный агрегированный отчёт по интервью.
    """
    interview_id: str = Field(..., description="UUID интервью")
    final_score: float = Field(0.0, description="Итоговый балл кандидата")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Сводка по анализу")
    strengths: List[str] = Field(default_factory=list, description="Сильные стороны")
    risks: List[str] = Field(default_factory=list, description="Риски / красные флаги")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
