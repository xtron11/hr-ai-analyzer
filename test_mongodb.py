# -*- coding: utf-8 -*-
"""
Test MongoDB — insert data into all collections.
Run: python test_mongodb.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import os
from uuid import uuid4
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join("audio_module", ".env"))

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB  = os.getenv("MONGO_DB_NAME", "interview_platform")

from pymongo import MongoClient
import certifi

# tlsCAFile=certifi — явно указываем CA-сертификаты (fix для Windows)
client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,
    tlsCAFile=certifi.where(),
)
client.admin.command("ping")
db = client[MONGO_DB]

now = datetime.now(timezone.utc).isoformat()
interview_id = str(uuid4())

print("\n" + "=" * 55)
print("  MongoDB — test insert")
print(f"  DB: {MONGO_DB}")
print("=" * 55)

# ── 1. audio_analysis ────────────────────────────────────
doc_audio = {
    "interview_id": interview_id,
    "speech_rate": {
        "speech_rate_wpm": 142,
        "word_count": 387,
        "duration_sec": 163.5,
    },
    "pause_metrics": {
        "pause_count": 14,
        "total_pause_sec": 8.2,
        "avg_pause_sec": 0.59,
    },
    "pitch_metrics": {
        "mean_f0": 187.4,
        "min_f0": 98.1,
        "max_f0": 312.7,
    },
    "emotions_recognition": {
        "emotion": "neutral",
        "confidence": 0.81,
        "emotions_timeline": [
            {"time": 0, "emotion": "neutral"},
            {"time": 30, "emotion": "happy"},
        ],
    },
    "transcript_segments": [
        {"speaker": "candidate", "start_ms": 0, "end_ms": 5200, "text": "Добрый день, расскажу о своём опыте."},
        {"speaker": "candidate", "start_ms": 5200, "end_ms": 11000, "text": "Я работал с FastAPI и PostgreSQL три года."},
    ],
    "detected_language": "ru",
    "created_at": now,
}
r = db.audio_analysis.insert_one(doc_audio)
print(f"\n[+] audio_analysis")
print(f"    _id:          {r.inserted_id}")
print(f"    interview_id: {interview_id}")
print(f"    wpm:          {doc_audio['speech_rate']['speech_rate_wpm']}")
print(f"    emotion:      {doc_audio['emotions_recognition']['emotion']}")

# ── 2. text_analysis ─────────────────────────────────────
doc_text = {
    "interview_id": interview_id,
    "parsed": {
        "qa_items": [
            {"question": "Расскажите об опыте с FastAPI", "answer": "3 года, продакшн проекты"},
        ],
        "facts": ["3 года опыта FastAPI", "знание PostgreSQL"],
        "unclear_points": [],
        "quality_flags": {"low_confidence_transcript": False},
    },
    "scored": {
        "scores": {
            "hard_skills":   {"value": 8, "rationale": "Уверенные ответы по технологиям"},
            "communication": {"value": 7, "rationale": "Чёткая структура речи"},
            "culture_fit":   {"value": 7, "rationale": "Командный подход"},
        },
        "recommendation": {"decision": "hire", "next_steps": ["Техническое интервью"]},
    },
    "detected_language": "ru",
    "transcript_segments_count": 2,
    "created_at": now,
}
r = db.text_analysis.insert_one(doc_text)
print(f"\n[+] text_analysis")
print(f"    _id:          {r.inserted_id}")
print(f"    hard_skills:  {doc_text['scored']['scores']['hard_skills']['value']}/10")
print(f"    decision:     {doc_text['scored']['recommendation']['decision']}")

# ── 3. aggregated_reports ─────────────────────────────────
doc_report = {
    "interview_id": interview_id,
    "final_score": 7.5,
    "summary": {
        "short": "Сильный кандидат с хорошим техническим бэкграундом",
        "detailed": "Кандидат продемонстрировал уверенное владение Python/FastAPI, грамотную речь и командный подход.",
    },
    "strengths": ["FastAPI опыт", "PostgreSQL", "чёткая коммуникация"],
    "risks": ["нет опыта с микросервисами"],
    "follow_up_questions": ["Расскажите о самом сложном проекте?"],
    "scores": doc_text["scored"]["scores"],
    "recommendation": doc_text["scored"]["recommendation"],
    "generated_at": now,
}
r = db.aggregated_reports.insert_one(doc_report)
print(f"\n[+] aggregated_reports")
print(f"    _id:          {r.inserted_id}")
print(f"    final_score:  {doc_report['final_score']}/10")
print(f"    decision:     {doc_report['recommendation']['decision']}")

# ── Читаем обратно ────────────────────────────────────────
print("\n" + "-" * 55)
print("  Read back from MongoDB:")
print("-" * 55)

a = db.audio_analysis.find_one({"interview_id": interview_id})
print(f"\n[?] audio_analysis:       wpm={a['speech_rate']['speech_rate_wpm']}, lang={a['detected_language']}")

t = db.text_analysis.find_one({"interview_id": interview_id})
print(f"[?] text_analysis:        hard_skills={t['scored']['scores']['hard_skills']['value']}/10")

rep = db.aggregated_reports.find_one({"interview_id": interview_id})
print(f"[?] aggregated_reports:   final_score={rep['final_score']}/10, decision={rep['recommendation']['decision']}")

print("\n" + "=" * 55)
print("  MongoDB OK — check Atlas UI!")
print(f"  interview_id: {interview_id}")
print(f"  DB:           {MONGO_DB}")
print("=" * 55 + "\n")

client.close()
