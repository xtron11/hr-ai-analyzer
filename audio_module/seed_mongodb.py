"""
Скрипт для проверки подключения к MongoDB и заполнения тестовыми данными.

Запуск из папки audio_module:
    python seed_mongodb.py

Что делает:
  1. Проверяет соединение с MongoDB Atlas (ping)
  2. Вставляет по 2 документа в каждую коллекцию:
       audio_analysis, text_analysis, video_analysis, aggregated_reports
  3. Читает и выводит вставленные документы
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Добавляем корень audio_module в sys.path чтобы найти app.config
sys.path.insert(0, str(Path(__file__).parent))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB_NAME", "interview_platform")

# ─────────────────────────────────────────────────────────────
#  Тестовые данные
# ─────────────────────────────────────────────────────────────

SEED_AUDIO_ANALYSIS = [
    {
        "interview_id": "test-interview-001",
        "speech_rate": {
            "speech_rate_wpm": 142.5,
            "speech_rate_method": "asr_words",
            "word_count": 285,
            "duration_sec": 120.0,
        },
        "pause_metrics": {
            "total_pauses": 8,
            "total_pause_time_sec": 14.2,
            "avg_pause_duration_sec": 1.78,
            "long_pauses_count": 2,
            "pause_rate_per_min": 4.0,
            "pause_threshold_sec": 1.5,
        },
        "pitch_metrics": {
            "avg_pitch": 185.3,
            "min_pitch": 110.0,
            "max_pitch": 310.0,
            "std_pitch": 42.1,
            "pitch_range": 200.0,
            "voiced_ratio": 0.72,
        },
        "affect_dimensions": {
            "valence": 0.61,
            "arousal": 0.48,
            "dominance": 0.55,
        },
        "acoustic_features": {
            "mfcc_mean": [12.3, -4.1, 2.8, 0.5, -1.2, 0.9, 3.4, -0.7],
            "rms_energy": 0.043,
            "zcr_mean": 0.087,
        },
        "emotions_recognition": {
            "emotion": "neutral",
            "confidence": 0.78,
            "emotions_timeline": [
                {"start_sec": 0.0,  "end_sec": 30.0, "emotion": "neutral",   "confidence": 0.82},
                {"start_sec": 30.0, "end_sec": 75.0, "emotion": "happy",     "confidence": 0.65},
                {"start_sec": 75.0, "end_sec": 120.0,"emotion": "neutral",   "confidence": 0.77},
            ],
        },
        "complex_emotions": {
            "confidence_level": "high",
            "stress_level": "low",
            "engagement": 0.71,
        },
        "transcript_segments": [
            {"start": 0.0,  "end": 15.0, "text": "Здравствуйте, расскажу о своём опыте."},
            {"start": 15.0, "end": 45.0, "text": "Я работал три года backend-разработчиком в финтех-компании."},
            {"start": 45.0, "end": 90.0, "text": "Основной стек: Python, FastAPI, PostgreSQL, Redis."},
        ],
        "detected_language": "ru",
        "created_at": datetime.now(timezone.utc),
    },
    {
        "interview_id": "test-interview-002",
        "speech_rate": {
            "speech_rate_wpm": 98.0,
            "speech_rate_method": "asr_words",
            "word_count": 196,
            "duration_sec": 120.0,
        },
        "pause_metrics": {
            "total_pauses": 15,
            "total_pause_time_sec": 28.5,
            "avg_pause_duration_sec": 1.9,
            "long_pauses_count": 6,
            "pause_rate_per_min": 7.5,
            "pause_threshold_sec": 1.5,
        },
        "pitch_metrics": {
            "avg_pitch": 210.0,
            "min_pitch": 140.0,
            "max_pitch": 380.0,
            "std_pitch": 65.3,
            "pitch_range": 240.0,
            "voiced_ratio": 0.61,
        },
        "affect_dimensions": {
            "valence": 0.38,
            "arousal": 0.72,
            "dominance": 0.31,
        },
        "acoustic_features": {
            "mfcc_mean": [8.1, -6.3, 1.4, 1.9, -2.7, 0.3, 2.1, -1.4],
            "rms_energy": 0.031,
            "zcr_mean": 0.112,
        },
        "emotions_recognition": {
            "emotion": "fear",
            "confidence": 0.64,
            "emotions_timeline": [
                {"start_sec": 0.0,  "end_sec": 40.0, "emotion": "nervous",   "confidence": 0.70},
                {"start_sec": 40.0, "end_sec": 80.0, "emotion": "fear",      "confidence": 0.58},
                {"start_sec": 80.0, "end_sec": 120.0,"emotion": "neutral",   "confidence": 0.55},
            ],
        },
        "complex_emotions": {
            "confidence_level": "low",
            "stress_level": "high",
            "engagement": 0.45,
        },
        "transcript_segments": [
            {"start": 0.0,  "end": 20.0, "text": "Эм... добрый день. Я немного волнуюсь."},
            {"start": 20.0, "end": 60.0, "text": "У меня опыт... около года в веб-разработке."},
            {"start": 60.0, "end": 120.0,"text": "Работал с JavaScript и немного с Python."},
        ],
        "detected_language": "ru",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=3),
    },
]

SEED_TEXT_ANALYSIS = [
    {
        "interview_id": "test-interview-001",
        "source": "transcript",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
        "keyword_scores": {
            "python":     {"count": 4, "relevance": 0.92},
            "fastapi":    {"count": 2, "relevance": 0.88},
            "postgresql": {"count": 3, "relevance": 0.85},
        },
        "psych_traits": {
            "leadership":    0.72,
            "teamwork":      0.88,
            "communication": 0.79,
            "stress_resist": 0.81,
        },
        "llm_summary": "Кандидат демонстрирует уверенный технический уровень, чёткую коммуникацию и реальный продуктовый опыт.",
        "created_at": datetime.now(timezone.utc),
    },
    {
        "interview_id": "test-interview-002",
        "source": "transcript",
        "skills": ["JavaScript", "HTML", "CSS", "Python (базовый)"],
        "keyword_scores": {
            "javascript": {"count": 5, "relevance": 0.75},
            "html":        {"count": 2, "relevance": 0.50},
            "python":      {"count": 1, "relevance": 0.40},
        },
        "psych_traits": {
            "leadership":    0.35,
            "teamwork":      0.62,
            "communication": 0.51,
            "stress_resist": 0.28,
        },
        "llm_summary": "Кандидат с базовым опытом, заметно волнуется. Навыки ещё формируются; требует менторства.",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=3),
    },
]

SEED_VIDEO_ANALYSIS = [
    {
        "interview_id": "test-interview-001",
        "facial": {
            "dominant_expression": "neutral",
            "smile_ratio": 0.31,
            "expression_timeline": [
                {"sec": 0,  "expression": "neutral", "confidence": 0.85},
                {"sec": 30, "expression": "smile",   "confidence": 0.72},
                {"sec": 60, "expression": "neutral", "confidence": 0.80},
            ],
        },
        "gaze": {
            "eye_contact_ratio": 0.74,
            "avg_gaze_deviation_deg": 8.2,
            "gaze_stability": "stable",
        },
        "pose_gesture": {
            "posture": "upright",
            "head_movement_index": 0.22,
            "hand_gesture_count": 14,
        },
        "created_at": datetime.now(timezone.utc),
    },
    {
        "interview_id": "test-interview-002",
        "facial": {
            "dominant_expression": "nervous",
            "smile_ratio": 0.08,
            "expression_timeline": [
                {"sec": 0,  "expression": "nervous", "confidence": 0.77},
                {"sec": 45, "expression": "neutral",  "confidence": 0.55},
                {"sec": 90, "expression": "nervous",  "confidence": 0.68},
            ],
        },
        "gaze": {
            "eye_contact_ratio": 0.41,
            "avg_gaze_deviation_deg": 22.7,
            "gaze_stability": "unstable",
        },
        "pose_gesture": {
            "posture": "slouched",
            "head_movement_index": 0.61,
            "hand_gesture_count": 5,
        },
        "created_at": datetime.now(timezone.utc) - timedelta(hours=3),
    },
]

SEED_AGGREGATED_REPORTS = [
    {
        "interview_id": "test-interview-001",
        "final_score": 82.5,
        "summary": {
            "audio_score":  78.0,
            "text_score":   88.0,
            "video_score":  81.0,
            "overall_band": "B+",
        },
        "strengths": [
            "Уверенная речь, оптимальный темп (142 wpm)",
            "Богатый технический стек (Python / FastAPI / PostgreSQL)",
            "Хороший зрительный контакт (74%)",
        ],
        "risks": [
            "Небольшое количество длинных пауз (2 шт.)",
        ],
        "recommendation": "hire",
        "generated_at": datetime.now(timezone.utc),
    },
    {
        "interview_id": "test-interview-002",
        "final_score": 41.0,
        "summary": {
            "audio_score":  35.0,
            "text_score":   48.0,
            "video_score":  40.0,
            "overall_band": "D",
        },
        "strengths": [
            "Базовый JS-опыт есть",
            "Честность в ответах",
        ],
        "risks": [
            "Высокий стресс-уровень (частые паузы, нестабильный взгляд)",
            "Недостаточно навыков для позиции",
            "Слабый зрительный контакт (41%)",
        ],
        "recommendation": "reject",
        "generated_at": datetime.now(timezone.utc) - timedelta(hours=3),
    },
]


# ─────────────────────────────────────────────────────────────
#  Логика
# ─────────────────────────────────────────────────────────────

async def check_connection(client: AsyncIOMotorClient) -> bool:
    try:
        await client.admin.command("ping")
        return True
    except Exception as e:
        print(f"  [ERROR] Ping не прошёл: {e}")
        return False


async def seed_collection(db, name: str, docs: list):
    col = db[name]
    result = await col.insert_many(docs)
    print(f"  [{name}] вставлено {len(result.inserted_ids)} документов")
    return result.inserted_ids


async def read_collection(db, name: str):
    col = db[name]
    docs = await col.find().to_list(length=100)
    return docs


async def main():
    print("=" * 60)
    print(" MongoDB Atlas — проверка и заполнение тестовыми данными")
    print("=" * 60)
    print(f"  URI : {MONGO_URI[:40]}...")
    print(f"  DB  : {DB_NAME}")
    print()

    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    db = client[DB_NAME]

    # 1. Проверка соединения
    print("── Проверка соединения ──────────────────────────────────")
    ok = await check_connection(client)
    if not ok:
        print("Не удалось подключиться к MongoDB. Проверь MONGO_URI в .env")
        client.close()
        return
    print("  [OK] MongoDB доступна\n")

    # 2. Показываем текущее состояние коллекций
    print("── Текущее состояние коллекций ──────────────────────────")
    for col_name in ["audio_analysis", "text_analysis", "video_analysis", "aggregated_reports"]:
        count = await db[col_name].count_documents({})
        print(f"  {col_name:<25} {count} документов")
    print()

    # 3. Вставка тестовых данных
    print("── Вставка тестовых данных ───────────────────────────────")
    await seed_collection(db, "audio_analysis",    SEED_AUDIO_ANALYSIS)
    await seed_collection(db, "text_analysis",     SEED_TEXT_ANALYSIS)
    await seed_collection(db, "video_analysis",    SEED_VIDEO_ANALYSIS)
    await seed_collection(db, "aggregated_reports", SEED_AGGREGATED_REPORTS)
    print()

    # 4. Читаем и показываем то, что лежит в БД
    print("── Данные в БД после seed ────────────────────────────────")

    print("\n[audio_analysis]")
    for doc in await read_collection(db, "audio_analysis"):
        doc["_id"] = str(doc["_id"])
        print(f"  interview_id={doc['interview_id']}  "
              f"speech_rate={doc['speech_rate']['speech_rate_wpm']} wpm  "
              f"emotion={doc['emotions_recognition']['emotion']}  "
              f"lang={doc['detected_language']}")

    print("\n[text_analysis]")
    for doc in await read_collection(db, "text_analysis"):
        doc["_id"] = str(doc["_id"])
        print(f"  interview_id={doc['interview_id']}  "
              f"source={doc.get('source', '?')}  "
              f"skills={doc.get('skills', [])}")

    print("\n[video_analysis]")
    for doc in await read_collection(db, "video_analysis"):
        doc["_id"] = str(doc["_id"])
        facial = doc.get("facial", {})
        gaze   = doc.get("gaze", {})
        print(f"  interview_id={doc['interview_id']}  "
              f"expression={facial.get('dominant_expression', '?')}  "
              f"eye_contact={gaze.get('eye_contact_ratio', 0):.0%}")

    print("\n[aggregated_reports]")
    for doc in await read_collection(db, "aggregated_reports"):
        doc["_id"] = str(doc["_id"])
        summary = doc.get("summary", {})
        print(f"  interview_id={doc['interview_id']}  "
              f"final_score={doc.get('final_score', '?')}  "
              f"band={summary.get('overall_band', '?')}  "
              f"recommendation={doc.get('recommendation', '?')}")

    print()
    print("── Итоговое состояние коллекций ─────────────────────────")
    for col_name in ["audio_analysis", "text_analysis", "video_analysis", "aggregated_reports"]:
        count = await db[col_name].count_documents({})
        print(f"  {col_name:<25} {count} документов")

    client.close()
    print("\n[DONE] Готово! Открой MongoDB Atlas → Browse Collections чтобы увидеть данные.")


if __name__ == "__main__":
    asyncio.run(main())
