"""
Interview Platform — Audio Analysis API

Эндпоинты:
  POST /analyze-audio              — загрузка и анализ аудио
  GET  /analysis/{interview_id}    — результат аудио-анализа (из MongoDB/кэша)
  POST /vacancies                  — создать вакансию (Supabase)
  GET  /vacancies                  — список вакансий
  POST /interviews                 — создать интервью
  GET  /interviews/{id}            — получить интервью
  GET  /interviews/{id}/artifacts  — артефакты интервью
  GET  /interviews/{id}/report     — агрегированный отчёт
  GET  /health                     — статус всех сервисов

Data Flow (из диаграммы):
  1) Upload inputs → файл в Storage
  2) Insert files row (метаданные) → Supabase
  3) Insert interview_artifacts rows → Supabase
  4) ML-анализ (pipeline) → результат в MongoDB
  5) Кэширование → Redis
"""

import gc
import hashlib
import logging
import os
import subprocess
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.config import settings
from app.database.mongodb import mongodb
from app.database.supabase_client import supabase_client
from app.database.redis_client import redis_client
from app.database.rabbitmq import rabbitmq_client
from app.storage import save_file, save_to_json

# ML-сервисы (без изменений)
from app.services.audio_preprocessor import audio_preprocessor
from app.services.speech_rate_service import speech_rate_service
from app.services.speech_pauses_service import speech_pauses_service
from app.services.speech_pitch_service import speech_pitch_service
from app.services.emotion_recognition_service import emotion_recognition_service
from app.services.complex_emotion_service import complex_emotion_service
from app.services.affect_dimensions_service import affect_dimensions_service
from app.services.opensmile_service import opensmile_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("main")

VIDEO_MIME_TYPES = {
    "video/mp4", "video/mpeg", "video/webm", "video/avi",
    "video/quicktime", "video/x-msvideo", "video/x-matroska",
}


def extract_audio_from_video(video_path: str) -> str:
    """Извлекает аудио из видео через ffmpeg. Возвращает путь к WAV-файлу."""
    wav_path = video_path + "_extracted.wav"
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn",                  # без видео
        "-acodec", "pcm_s16le", # WAV PCM
        "-ar", "16000",         # 16kHz для ML моделей
        "-ac", "1",             # моно
        wav_path,
        "-y",                   # перезаписать если существует
        "-loglevel", "error",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"Аудио извлечено из видео: {wav_path}")
        return wav_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg ошибка: {e.stderr.decode()}")


# ═══════════════════════════════════════════════════════════
#  Lifespan: подключение/отключение всех сервисов
# ═══════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / Shutdown lifecycle для всех внешних сервисов."""
    logger.info("=" * 60)
    logger.info("Interview Platform — Audio Module запускается")
    logger.info("=" * 60)

    # Подключаемся ко всем сервисам (с graceful degradation)
    await mongodb.connect()
    await supabase_client.connect()
    await redis_client.connect()
    await rabbitmq_client.connect()

    # Логируем статус
    logger.info(f"  MongoDB:   {'✓' if mongodb.is_connected else '✗ (degraded)'}")
    logger.info(f"  Supabase:  {'✓' if supabase_client.is_connected else '✗ (degraded)'}")
    logger.info(f"  Redis:     {'✓' if redis_client.is_connected else '✗ (no cache)'}")
    logger.info(f"  RabbitMQ:  {'✓' if rabbitmq_client.is_connected else '✗ (sync mode)'}")
    logger.info("=" * 60)

    yield  # Приложение работает

    # Shutdown
    logger.info("Завершение работы...")
    await mongodb.disconnect()
    await supabase_client.disconnect()
    await redis_client.disconnect()
    await rabbitmq_client.disconnect()


app = FastAPI(
    title="Interview Platform — Audio Analysis",
    version="2.0.0",
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════
#  POST /analyze-audio — Основной эндпоинт анализа
# ═══════════════════════════════════════════════════════════

@app.post("/analyze-audio")
async def analyze_audio(
    file: UploadFile = File(...),
    interview_id: Optional[str] = Form(None),
    vacancy_id: Optional[str] = Form(None),
):
    """
    Загрузка аудио или видео и запуск анализа.
    Видео автоматически конвертируется в WAV через ffmpeg.
    Если RabbitMQ доступен — задача отправляется в очередь (async).
    Иначе — анализ выполняется синхронно.
    """
    # 1. Генерируем/используем interview_id
    if not interview_id:
        interview_id = str(uuid.uuid4())

    # 2. Определяем суффикс по типу файла
    is_video = file.content_type in VIDEO_MIME_TYPES
    suffix = ".mp4" if is_video else ".wav"

    # 3. Сохраняем файл во временную директорию
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file_bytes = b""
        while content := await file.read(1024 * 1024):
            tmp.write(content)
            file_bytes += content
        tmp_path = tmp.name

    # 4. Если видео — извлекаем аудио
    wav_path = tmp_path
    if is_video:
        try:
            wav_path = extract_audio_from_video(tmp_path)
            logger.info(f"Видео конвертировано в WAV: {interview_id}")
        except RuntimeError as e:
            os.remove(tmp_path)
            from fastapi import HTTPException
            raise HTTPException(422, detail=f"Ошибка обработки видео: {e}")

    file_size = len(file_bytes)
    file_checksum = hashlib.sha256(file_bytes).hexdigest()

    try:
        # 3. Сохраняем файл в Object Storage
        storage_key, checksum, size = save_file(
            interview_id=interview_id,
            artifact_type="audio_recording",
            data=file_bytes,
            original_name=file.filename or "audio.wav",
            content_type=file.content_type,
        )
        del file_bytes  # Освобождаем RAM

        # 4. Supabase: создаём записи (если подключен)
        file_record = await supabase_client.create_file_record(
            storage_provider=settings.STORAGE_PROVIDER,
            storage_key=storage_key,
            original_name=file.filename or "audio.wav",
            mime_type=file.content_type,
            size_bytes=file_size,
            checksum_sha256=file_checksum,
        )

        if file_record:
            await supabase_client.create_artifact(
                interview_id=interview_id,
                file_id=file_record["id"],
                artifact_type="audio_recording",
                direction="input",
            )
            await supabase_client.update_interview_status(
                interview_id, "audio_analyzing"
            )

        # 5. RabbitMQ: отправляем в очередь ИЛИ анализируем синхронно
        if rabbitmq_client.is_connected:
            # Async mode: отправляем задачу аудио-воркеру
            published = await rabbitmq_client.publish_audio_task(
                interview_id=interview_id,
                file_path=wav_path,
            )
            if published:
                return {
                    "status": "queued",
                    "interview_id": interview_id,
                    "message": "Задача отправлена в очередь. Результат: GET /analysis/{interview_id}",
                    "storage_key": storage_key,
                }

        # Sync mode (fallback): анализируем прямо здесь
        logger.info(f"Синхронный анализ: {interview_id}")

        waveform, sample_rate, duration = audio_preprocessor.process(wav_path)

        analysis_rate = speech_rate_service.analyze(waveform, sample_rate, duration)
        analysis_pauses = speech_pauses_service.analyze(waveform, sample_rate, duration)
        analysis_pitch = speech_pitch_service.analyze(waveform, sample_rate)
        analysis_emotion = emotion_recognition_service.analyze_file(wav_path)
        analysis_affect = affect_dimensions_service.analyze(
            waveform=waveform, sample_rate=sample_rate,
            duration_sec=duration, segment_sec=5.0, hop_sec=5.0,
        )
        analysis_opensmile = opensmile_service.analyze(
            waveform=waveform, sample_rate=sample_rate,
            duration_sec=duration, segment_sec=5.0, hop_sec=5.0,
        )
        analysis_complex = complex_emotion_service.analyze(
            transcript_segments=analysis_rate.get("transcript_segments", []),
            duration_sec=duration,
            speech_rate_wpm=analysis_rate.get("speech_rate_wpm"),
            pitch_metrics=analysis_pitch,
            affect_dimensions=analysis_affect,
            opensmile_features=analysis_opensmile,
            segment_sec=5.0, hop_sec=5.0,
        )

        transcript_segments = analysis_rate.get("transcript_segments", [])
        detected_language = analysis_rate.get("detected_language", "unknown")

        # Формируем результат
        result = {
            "interview_id": interview_id,
            "speech_rate": {
                "speech_rate_wpm": analysis_rate.get("speech_rate_wpm"),
                "speech_rate_method": analysis_rate.get("speech_rate_method", "asr_words"),
                "word_count": analysis_rate.get("word_count"),
                "duration_sec": duration,
            },
            "pause_metrics": analysis_pauses,
            "pitch_metrics": analysis_pitch,
            "affect_dimensions": analysis_affect,
            "acoustic_features": analysis_opensmile,
            "emotions_recognition": {
                "emotion": analysis_emotion["emotion"],
                "confidence": analysis_emotion["confidence"],
                "emotions_timeline": analysis_emotion["emotions_timeline"],
            },
            "complex_emotions": analysis_complex,
            "transcript_segments": transcript_segments,
            "detected_language": detected_language,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Сохраняем аудио-анализ в MongoDB
        mongo_id = await mongodb.insert_audio_analysis(result)

        # Кэшируем в Redis
        await redis_client.set_cached(redis_client.audio_key(interview_id), result)

        # JSON fallback (обратная совместимость)
        result_with_id = {"_id": mongo_id or str(uuid.uuid4()), **result}
        save_to_json(result_with_id)

        # Диспатч транскрипта в text_analysis_queue для LLM-анализа
        if rabbitmq_client.is_connected and transcript_segments:
            transcript_text = " ".join(
                s.get("text", "") for s in transcript_segments
            )
            await rabbitmq_client.publish_text_task(
                interview_id=interview_id,
                transcript_segments=transcript_segments,
                transcript_text=transcript_text,
                vacancy_id=vacancy_id,
                detected_language=detected_language,
            )
            logger.info(f"Транскрипт отправлен в text_analysis_queue: {interview_id}")
            # Статус обновит text_worker после LLM-анализа
        else:
            await supabase_client.update_interview_status(interview_id, "audio_completed")

        return {
            "status": "audio_completed",
            "interview_id": interview_id,
            "storage_key": storage_key,
            "text_analysis": "queued" if rabbitmq_client.is_connected and transcript_segments else "skipped",
            **result,
        }

    finally:
        if 'waveform' in locals():
            del waveform
        gc.collect()
        # Удаляем временные файлы (wav_path — только если не передан воркеру)
        if not rabbitmq_client.is_connected:
            if os.path.exists(wav_path):
                os.remove(wav_path)
            if is_video and os.path.exists(tmp_path):
                os.remove(tmp_path)


# ═══════════════════════════════════════════════════════════
#  GET /analysis/{interview_id}
# ═══════════════════════════════════════════════════════════

@app.get("/analysis/{interview_id}")
async def get_analysis(interview_id: str):
    """Получить результат аудио-анализа (Redis кэш → MongoDB)."""
    # 1. Проверяем кэш
    cached = await redis_client.get_cached(redis_client.audio_key(interview_id))
    if cached:
        return {"source": "cache", **cached}

    # 2. Читаем из MongoDB
    doc = await mongodb.get_audio_analysis(interview_id)
    if doc:
        await redis_client.set_cached(redis_client.audio_key(interview_id), doc)
        return {"source": "mongodb", **doc}

    raise HTTPException(status_code=404, detail="Анализ не найден")


# ═══════════════════════════════════════════════════════════
#  Vacancies (Supabase)
# ═══════════════════════════════════════════════════════════

@app.post("/vacancies")
async def create_vacancy(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    corporate_values: Optional[str] = Form(None),
):
    """Создать вакансию."""
    if not supabase_client.is_connected:
        raise HTTPException(503, "Supabase не подключен")
    result = await supabase_client.create_vacancy(title, description, corporate_values)
    if not result:
        raise HTTPException(500, "Ошибка создания вакансии")
    return result


@app.get("/vacancies")
async def list_vacancies():
    """Список вакансий."""
    return await supabase_client.get_vacancies()


# ═══════════════════════════════════════════════════════════
#  Interviews (Supabase)
# ═══════════════════════════════════════════════════════════

@app.post("/interviews")
async def create_interview(
    vacancy_id: str = Form(...),
    candidate_external_ref: Optional[str] = Form(None),
):
    """Создать интервью."""
    if not supabase_client.is_connected:
        raise HTTPException(503, "Supabase не подключен")
    result = await supabase_client.create_interview(vacancy_id, candidate_external_ref)
    if not result:
        raise HTTPException(500, "Ошибка создания интервью")
    return result


@app.get("/interviews/{interview_id}")
async def get_interview(interview_id: str):
    """Получить интервью."""
    # Кэш
    cached = await redis_client.get_cached(redis_client.interview_key(interview_id))
    if cached:
        return cached
    if not supabase_client.is_connected:
        raise HTTPException(503, "Supabase не подключен")
    result = await supabase_client.get_interview(interview_id)
    if not result:
        raise HTTPException(404, "Интервью не найдено")
    await redis_client.set_cached(redis_client.interview_key(interview_id), result, ttl=300)
    return result


@app.get("/interviews/{interview_id}/artifacts")
async def get_artifacts(interview_id: str):
    """Получить артефакты интервью."""
    if not supabase_client.is_connected:
        raise HTTPException(503, "Supabase не подключен")
    return await supabase_client.get_artifacts_by_interview(interview_id)


# ═══════════════════════════════════════════════════════════
#  Aggregated Report (MongoDB)
# ═══════════════════════════════════════════════════════════

@app.get("/interviews/{interview_id}/report")
async def get_report(interview_id: str):
    """Получить агрегированный отчёт."""
    cached = await redis_client.get_cached(redis_client.report_key(interview_id))
    if cached:
        return {"source": "cache", **cached}
    doc = await mongodb.get_aggregated_report(interview_id)
    if doc:
        await redis_client.set_cached(redis_client.report_key(interview_id), doc)
        return {"source": "mongodb", **doc}
    raise HTTPException(404, "Отчёт не найден")


# ═══════════════════════════════════════════════════════════
#  Health Check
# ═══════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """Статус всех сервисов — готовность к нагрузке."""
    return {
        "status": "ok",
        "services": {
            "mongodb": {"connected": mongodb.is_connected},
            "supabase": {"connected": supabase_client.is_connected},
            "redis": {"connected": redis_client.is_connected},
            "rabbitmq": {"connected": rabbitmq_client.is_connected},
        },
        "storage_provider": settings.STORAGE_PROVIDER,
        "degradation_mode": not all([
            mongodb.is_connected,
            supabase_client.is_connected,
            redis_client.is_connected,
            rabbitmq_client.is_connected,
        ]),
    }