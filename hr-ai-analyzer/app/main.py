"""
HR AI Analyzer — Text Analysis API

Endpoints:
  POST /analyze-text          — прямой анализ транскрипта (sync, без очереди)
  GET  /analysis/{id}         — результат текстового анализа из MongoDB
  GET  /reports/{id}          — агрегированный отчёт из MongoDB
  GET  /reports               — список всех отчётов
  GET  /health                — статус сервисов
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.database.mongodb import mongodb
from app.database.supabase_client import supabase_client
from app.database.redis_client import redis_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("hr_main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("HR AI Analyzer запускается")
    logger.info("=" * 60)
    await mongodb.connect()
    await supabase_client.connect()
    await redis_client.connect()
    logger.info(f"  MongoDB:  {'✓' if mongodb.is_connected else '✗'}")
    logger.info(f"  Supabase: {'✓' if supabase_client.is_connected else '✗'}")
    logger.info(f"  Redis:    {'✓' if redis_client.is_connected else '✗'}")
    logger.info(f"  Ollama:   {settings.OLLAMA_URL}")
    logger.info("=" * 60)
    yield
    await mongodb.disconnect()
    await supabase_client.disconnect()
    await redis_client.disconnect()


app = FastAPI(
    title="HR AI Analyzer",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request models ────────────────────────────────────────

class AnalyzeTextRequest(BaseModel):
    interview_id: str
    transcript_text: str
    transcript_segments: list = []
    vacancy: dict = {}
    detected_language: str = "unknown"


# ── POST /analyze-text ────────────────────────────────────

@app.post("/analyze-text")
async def analyze_text(req: AnalyzeTextRequest):
    """Синхронный LLM-анализ транскрипта."""
    import asyncio
    from app.workers.text_worker import run_llm_pipeline

    logger.info(f"Анализ текста: interview_id={req.interview_id}")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            run_llm_pipeline,
            req.transcript_text,
            req.transcript_segments,
            req.vacancy,
        )

        now = datetime.now(timezone.utc).isoformat()

        text_doc = {
            "interview_id": req.interview_id,
            "parsed": result["parsed"],
            "scored": result["scored"],
            "detected_language": req.detected_language,
            "transcript_segments_count": len(req.transcript_segments),
            "created_at": now,
        }
        await mongodb.insert_text_analysis(text_doc)

        report_doc = {
            "interview_id": req.interview_id,
            **result["report"],
            "scores": result["scored"].get("scores"),
            "recommendation": result["scored"].get("recommendation"),
            "generated_at": now,
        }
        await mongodb.insert_aggregated_report(report_doc)

        await redis_client.set_cached(redis_client.text_key(req.interview_id), text_doc)
        await redis_client.set_cached(redis_client.report_key(req.interview_id), report_doc)
        await supabase_client.update_interview_status(req.interview_id, "completed")

        return {
            "status": "completed",
            "interview_id": req.interview_id,
            **result,
        }

    except Exception as e:
        logger.error(f"Ошибка анализа: {e}", exc_info=True)
        raise HTTPException(500, detail=f"Ошибка LLM-анализа: {str(e)}")


# ── GET /analysis/{interview_id} ──────────────────────────

@app.get("/analysis/{interview_id}")
async def get_text_analysis(interview_id: str):
    """Получить результат текстового анализа."""
    cached = await redis_client.get_cached(redis_client.text_key(interview_id))
    if cached:
        return {"source": "cache", **cached}
    doc = await mongodb.get_text_analysis(interview_id)
    if doc:
        return {"source": "mongodb", **doc}
    raise HTTPException(404, "Текстовый анализ не найден")


# ── GET /reports/{interview_id} ───────────────────────────

@app.get("/reports/{interview_id}")
async def get_report(interview_id: str):
    """Получить агрегированный отчёт."""
    cached = await redis_client.get_cached(redis_client.report_key(interview_id))
    if cached:
        return {"source": "cache", **cached}
    doc = await mongodb.get_aggregated_report(interview_id)
    if doc:
        return {"source": "mongodb", **doc}
    raise HTTPException(404, "Отчёт не найден")


# ── GET /reports ──────────────────────────────────────────

@app.get("/reports")
async def list_reports(limit: int = 20):
    """Список последних отчётов."""
    return await mongodb.get_all_reports(limit=limit)


# ── GET /health ───────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "services": {
            "mongodb": {"connected": mongodb.is_connected},
            "supabase": {"connected": supabase_client.is_connected},
            "redis": {"connected": redis_client.is_connected},
            "ollama": {"url": settings.OLLAMA_URL, "model": settings.OLLAMA_MODEL},
        },
    }
