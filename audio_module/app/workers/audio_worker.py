"""
Воркер для обработки аудио-задач из RabbitMQ.
Запускается отдельным процессом: python -m app.workers.audio_worker

Получает задачи из очереди audio_analysis_queue, запускает пайплайн анализа,
сохраняет результат в MongoDB.
"""
import asyncio, gc, json, logging, os, sys
from datetime import datetime, timezone
from uuid import uuid4

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import settings
from app.database.mongodb import mongodb
from app.database.redis_client import redis_client
from app.database.rabbitmq import rabbitmq_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("audio_worker")


def run_analysis_pipeline(file_path: str) -> dict:
    """Запуск полного пайплайна аудио-анализа (синхронный, в отдельном потоке)."""
    from app.services.audio_preprocessor import audio_preprocessor
    from app.services.speech_rate_service import speech_rate_service
    from app.services.speech_pauses_service import speech_pauses_service
    from app.services.speech_pitch_service import speech_pitch_service
    from app.services.emotion_recognition_service import emotion_recognition_service
    from app.services.complex_emotion_service import complex_emotion_service
    from app.services.affect_dimensions_service import affect_dimensions_service
    from app.services.opensmile_service import opensmile_service

    waveform, sample_rate, duration = audio_preprocessor.process(file_path)

    analysis_rate = speech_rate_service.analyze(waveform, sample_rate, duration)
    analysis_pauses = speech_pauses_service.analyze(waveform, sample_rate, duration)
    analysis_pitch = speech_pitch_service.analyze(waveform, sample_rate)
    analysis_emotion = emotion_recognition_service.analyze_file(file_path)
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

    result = {
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
        "transcript_segments": analysis_rate.get("transcript_segments", []),
        "detected_language": analysis_rate.get("detected_language", "unknown"),
    }

    # Очистка памяти
    del waveform
    gc.collect()
    return result


async def process_audio_task(payload: dict):
    """Обработка одной задачи из очереди."""
    interview_id = payload.get("interview_id")
    file_path = payload.get("file_path")

    if not interview_id or not file_path:
        logger.error(f"Невалидный payload: {payload}")
        return

    logger.info(f"Начинаю анализ: interview_id={interview_id}")

    try:
        # Запускаем тяжёлый пайплайн в thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_analysis_pipeline, file_path)

        # Формируем MongoDB-документ
        document = {
            "interview_id": interview_id,
            **result,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Сохраняем в MongoDB
        mongo_id = await mongodb.insert_audio_analysis(document)

        # Обновляем кэш
        await redis_client.set_cached(redis_client.audio_key(interview_id), document)

        # Инвалидируем старый отчёт
        await redis_client.invalidate(redis_client.report_key(interview_id))

        # Диспатч транскрипта в text_analysis_queue
        transcript_segments = result.get("transcript_segments", [])
        detected_language = result.get("detected_language", "unknown")
        if transcript_segments:
            transcript_text = " ".join(s.get("text", "") for s in transcript_segments)
            await rabbitmq_client.publish_text_task(
                interview_id=interview_id,
                transcript_segments=transcript_segments,
                transcript_text=transcript_text,
                detected_language=detected_language,
            )
            logger.info(f"Транскрипт отправлен в text_analysis_queue: {interview_id}")

        logger.info(f"Анализ завершён: interview_id={interview_id}, mongo_id={mongo_id}")

    except Exception as e:
        logger.error(f"Ошибка анализа interview_id={interview_id}: {e}", exc_info=True)

    finally:
        # Удаляем временный файл
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


async def main():
    """Запуск воркера."""
    logger.info("Audio Worker запускается...")
    await mongodb.connect()
    await redis_client.connect()
    await rabbitmq_client.connect()

    if not rabbitmq_client.is_connected:
        logger.error("RabbitMQ не подключен — воркер не может работать")
        return

    logger.info(f"Слушаю очередь: {settings.AUDIO_QUEUE_NAME}")
    await rabbitmq_client.consume(settings.AUDIO_QUEUE_NAME, process_audio_task)


if __name__ == "__main__":
    asyncio.run(main())
