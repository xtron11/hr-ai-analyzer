"""
RabbitMQ воркер для текстового/LLM анализа интервью.
Запуск: python -m app.workers.text_worker

Получает из text_analysis_queue:
  {interview_id, transcript_segments, transcript_text, vacancy_id, detected_language}

Сохраняет в MongoDB:
  - text_analysis     (парсинг + оценки)
  - aggregated_reports (финальный отчёт)

Обновляет Supabase: interview status → "completed"
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import settings
from app.database.mongodb import mongodb
from app.database.supabase_client import supabase_client
from app.database.redis_client import redis_client
from app.database.rabbitmq import rabbitmq_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("text_worker")


def run_llm_pipeline(transcript_text: str, transcript_segments: list, vacancy: dict) -> dict:
    """Синхронный LLM-пайплайн: parse → score → report."""
    from app.services.parser import parse_transcript
    from app.services.scoring import score_candidate
    from app.services.report import generate_report

    # Формируем транскрипт с учётом сегментов
    if transcript_segments:
        full_text = "\n".join(
            f"[{s.get('speaker', 'Speaker')} {s.get('start_ms', 0)//1000}s]: {s.get('text', '')}"
            for s in transcript_segments
        )
    else:
        full_text = transcript_text or ""

    parsed = parse_transcript(full_text)
    scored = score_candidate(parsed, vacancy)
    report = generate_report(parsed, scored, vacancy)

    return {
        "parsed": parsed,
        "scored": scored,
        "report": report,
    }


async def process_text_task(payload: dict):
    """Обработка одного сообщения из очереди."""
    interview_id = payload.get("interview_id")
    transcript_segments = payload.get("transcript_segments", [])
    transcript_text = payload.get("transcript_text", "")
    vacancy = payload.get("vacancy", {})

    if not interview_id:
        logger.error(f"Невалидный payload (нет interview_id): {payload}")
        return

    logger.info(f"Текстовый анализ: interview_id={interview_id}")

    # Обновляем статус
    await supabase_client.update_interview_status(interview_id, "text_analyzing")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, run_llm_pipeline, transcript_text, transcript_segments, vacancy
        )

        now = datetime.now(timezone.utc).isoformat()

        # Сохраняем text_analysis в MongoDB
        text_doc = {
            "interview_id": interview_id,
            "parsed": result["parsed"],
            "scored": result["scored"],
            "detected_language": payload.get("detected_language", "unknown"),
            "transcript_segments_count": len(transcript_segments),
            "created_at": now,
        }
        await mongodb.insert_text_analysis(text_doc)

        # Сохраняем aggregated_report в MongoDB
        report_doc = {
            "interview_id": interview_id,
            **result["report"],
            "scores": result["scored"].get("scores"),
            "recommendation": result["scored"].get("recommendation"),
            "generated_at": now,
        }
        await mongodb.insert_aggregated_report(report_doc)

        # Кэшируем отчёт
        await redis_client.set_cached(redis_client.report_key(interview_id), report_doc)
        await redis_client.set_cached(redis_client.text_key(interview_id), text_doc)

        # Обновляем статус → completed
        await supabase_client.update_interview_status(interview_id, "completed")

        logger.info(f"Текстовый анализ завершён: interview_id={interview_id}")

    except Exception as e:
        logger.error(f"Ошибка текстового анализа {interview_id}: {e}", exc_info=True)
        await supabase_client.update_interview_status(interview_id, "text_analysis_failed")


async def main():
    logger.info("Text Worker запускается...")
    await mongodb.connect()
    await supabase_client.connect()
    await redis_client.connect()
    await rabbitmq_client.connect()

    if not rabbitmq_client.is_connected:
        logger.error("RabbitMQ не подключен — воркер завершает работу")
        return

    logger.info(f"Слушаю очередь: {settings.TEXT_QUEUE_NAME}")
    await rabbitmq_client.consume(settings.TEXT_QUEUE_NAME, process_text_task)


if __name__ == "__main__":
    asyncio.run(main())
