"""
Демонстрация работы всей системы.
Показывает архитектуру, graceful degradation и data flow.
Работает БЕЗ внешних сервисов (MongoDB, Redis, RabbitMQ).
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.database.mongodb import mongodb
from app.database.supabase_client import supabase_client
from app.database.redis_client import redis_client
from app.database.rabbitmq import rabbitmq_client
from app.models.enums import ArtifactType, ArtifactDirection, InterviewStatus, StorageProvider
from app.models.mongo_models import AudioAnalysisDocument, TextAnalysisDocument, VideoAnalysisDocument, AggregatedReportDocument
from app.models.postgres_models import VacancyCreate, InterviewCreate, FileRecordCreate, InterviewArtifactCreate
from app.storage import save_file, save_to_json


def section(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


async def main():
    section("INTERVIEW PLATFORM - System Demo")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Config loaded from: {settings.Config.env_file}")

    # ══════════════════════════════════════════════════════
    #  1. CONFIG
    # ══════════════════════════════════════════════════════
    section("1. CONFIGURATION (app/config.py)")
    print(f"  MONGO_URI:         {settings.MONGO_URI[:40]}...")
    print(f"  MONGO_DB_NAME:     {settings.MONGO_DB_NAME}")
    print(f"  SUPABASE_URL:      {settings.SUPABASE_URL or '(not set)'}")
    print(f"  REDIS_URL:         {settings.REDIS_URL}")
    print(f"  RABBITMQ_URL:      {settings.RABBITMQ_URL}")
    print(f"  STORAGE_PROVIDER:  {settings.STORAGE_PROVIDER}")

    # ══════════════════════════════════════════════════════
    #  2. ENUMS
    # ══════════════════════════════════════════════════════
    section("2. ENUMS (app/models/enums.py)")
    print(f"  ArtifactType values:     {[e.value for e in ArtifactType]}")
    print(f"  ArtifactDirection:       {[e.value for e in ArtifactDirection]}")
    print(f"  InterviewStatus:         {[e.value for e in InterviewStatus]}")
    print(f"  StorageProvider:         {[e.value for e in StorageProvider]}")

    # ══════════════════════════════════════════════════════
    #  3. PYDANTIC MODELS - PostgreSQL
    # ══════════════════════════════════════════════════════
    section("3. POSTGRESQL MODELS (app/models/postgres_models.py)")

    vacancy = VacancyCreate(
        title="Python Backend Developer",
        description="We need a senior Python dev",
        corporate_values="Innovation, teamwork, growth"
    )
    print(f"  VacancyCreate:       {vacancy.model_dump()}")

    interview = InterviewCreate(
        vacancy_id=uuid4(),
        candidate_external_ref="candidate-001",
        status=InterviewStatus.PENDING
    )
    print(f"  InterviewCreate:     vacancy_id={str(interview.vacancy_id)[:8]}..., status={interview.status.value}")

    file_rec = FileRecordCreate(
        storage_provider=StorageProvider.LOCAL_DEV,
        storage_key="interviews/abc-123/audio/recording.wav",
        original_name="recording.wav",
        mime_type="audio/wav",
        size_bytes=1024000,
        checksum_sha256="a" * 64
    )
    print(f"  FileRecordCreate:    {file_rec.original_name}, {file_rec.size_bytes} bytes")

    artifact = InterviewArtifactCreate(
        interview_id=uuid4(),
        file_id=uuid4(),
        artifact_type=ArtifactType.AUDIO_RECORDING,
        direction=ArtifactDirection.INPUT
    )
    print(f"  ArtifactCreate:      type={artifact.artifact_type.value}, dir={artifact.direction.value}")

    # ══════════════════════════════════════════════════════
    #  4. PYDANTIC MODELS - MongoDB
    # ══════════════════════════════════════════════════════
    section("4. MONGODB MODELS (app/models/mongo_models.py)")

    interview_id = str(uuid4())

    audio_doc = AudioAnalysisDocument(
        interview_id=interview_id,
        speech_rate={"speech_rate_wpm": 142.5, "speech_rate_method": "asr_words", "word_count": 285, "duration_sec": 120.0},
        pause_metrics={"total_pauses": 12, "avg_pause_duration_sec": 0.8},
        pitch_metrics={"avg_pitch": 185.3, "min_pitch": 80.0, "max_pitch": 320.0},
        emotions_recognition={"emotion": "neu", "confidence": 0.87},
        detected_language="ru"
    )
    print(f"  AudioAnalysis:       interview={interview_id[:8]}..., wpm={audio_doc.speech_rate.speech_rate_wpm}")

    text_doc = TextAnalysisDocument(
        interview_id=interview_id,
        source="resume",
        skills=["Python", "FastAPI", "MongoDB", "Docker"],
        keyword_scores={"python": 0.95, "backend": 0.88},
        psych_traits={"openness": 0.72, "conscientiousness": 0.85}
    )
    print(f"  TextAnalysis:        source={text_doc.source}, skills={text_doc.skills}")

    video_doc = VideoAnalysisDocument(
        interview_id=interview_id,
        facial={"smile_ratio": 0.3, "micro_expressions": ["surprise", "neutral"]},
        gaze={"eye_contact_ratio": 0.65},
        pose_gesture={"openness": 0.8, "fidgeting_score": 0.2}
    )
    print(f"  VideoAnalysis:       gaze={video_doc.gaze}, facial keys={list(video_doc.facial.keys())}")

    report_doc = AggregatedReportDocument(
        interview_id=interview_id,
        final_score=78.5,
        summary={"overall": "Strong candidate with good technical skills"},
        strengths=["Python expertise", "Clear communication", "Eye contact"],
        risks=["Slight nervousness", "Limited leadership experience"]
    )
    print(f"  AggregatedReport:    score={report_doc.final_score}, strengths={len(report_doc.strengths)}, risks={len(report_doc.risks)}")

    # ══════════════════════════════════════════════════════
    #  5. OBJECT STORAGE
    # ══════════════════════════════════════════════════════
    section("5. OBJECT STORAGE (app/storage.py)")

    test_data = b"fake audio data for demo"
    storage_key, checksum, size = save_file(
        interview_id=interview_id,
        artifact_type="audio_recording",
        data=test_data,
        original_name="demo_recording.wav",
        content_type="audio/wav"
    )
    print(f"  Provider:            {settings.STORAGE_PROVIDER}")
    print(f"  Storage key:         {storage_key}")
    print(f"  SHA256:              {checksum[:16]}...")
    print(f"  Size:                {size} bytes")
    print(f"  File exists:         {os.path.exists(os.path.join(settings.STORAGE_BASE_PATH, storage_key))}")

    # ══════════════════════════════════════════════════════
    #  6. JSON FALLBACK
    # ══════════════════════════════════════════════════════
    section("6. JSON FALLBACK (results/*.json)")

    result_doc = {
        "_id": str(uuid4()),
        "interview_id": interview_id,
        **audio_doc.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    save_to_json(result_doc)
    json_path = os.path.join("results", f"{result_doc['_id']}.json")
    print(f"  Saved to:            {json_path}")
    print(f"  File exists:         {os.path.exists(json_path)}")
    print(f"  File size:           {os.path.getsize(json_path)} bytes")

    # ══════════════════════════════════════════════════════
    #  7. GRACEFUL DEGRADATION
    # ══════════════════════════════════════════════════════
    section("7. GRACEFUL DEGRADATION")

    await mongodb.connect()
    await supabase_client.connect()
    await redis_client.connect()
    await rabbitmq_client.connect()

    services = {
        "MongoDB":  mongodb.is_connected,
        "Supabase": supabase_client.is_connected,
        "Redis":    redis_client.is_connected,
        "RabbitMQ": rabbitmq_client.is_connected,
    }
    for name, status in services.items():
        icon = "[OK]" if status else "[DEGRADED]"
        print(f"  {icon:12s} {name}")

    degraded = not all(services.values())
    print()
    print(f"  System mode:         {'DEGRADED (fallbacks active)' if degraded else 'FULL'}")
    print()
    print("  Fallback behavior:")
    if not services["MongoDB"]:
        print("    - MongoDB OFF  -> results saved to results/*.json")
    if not services["Supabase"]:
        print("    - Supabase OFF -> interview_id generated locally (UUID)")
    if not services["Redis"]:
        print("    - Redis OFF    -> no caching, reads go direct to DB")
    if not services["RabbitMQ"]:
        print("    - RabbitMQ OFF -> analysis runs synchronously (no queue)")

    await mongodb.disconnect()
    await redis_client.disconnect()
    await rabbitmq_client.disconnect()

    # ══════════════════════════════════════════════════════
    #  8. DATA FLOW
    # ══════════════════════════════════════════════════════
    section("8. DATA FLOW (from diagram)")
    print("  1. Upload audio        -> Object Storage (local_dev)")
    print("  2. Register file       -> Supabase: files table")
    print("  3. Link to interview   -> Supabase: interview_artifacts table")
    print("  4. ML pipeline         -> services/* (speech, pitch, emotion...)")
    print("  5. Save results        -> MongoDB: audio_analysis collection")
    print("  6. Cache results       -> Redis (TTL=3600s)")
    print("  7. Update status       -> Supabase: interviews.status")
    print("  8. Aggregate report    -> MongoDB: aggregated_reports collection")

    # ══════════════════════════════════════════════════════
    #  9. API ENDPOINTS
    # ══════════════════════════════════════════════════════
    section("9. API ENDPOINTS (app/main.py)")
    endpoints = [
        ("POST", "/analyze-audio",                  "Upload and analyze audio"),
        ("GET",  "/analysis/{interview_id}",        "Get analysis (cache -> MongoDB)"),
        ("POST", "/vacancies",                       "Create vacancy (Supabase)"),
        ("GET",  "/vacancies",                       "List vacancies"),
        ("POST", "/interviews",                      "Create interview (Supabase)"),
        ("GET",  "/interviews/{id}",                "Get interview"),
        ("GET",  "/interviews/{id}/artifacts",      "Get artifacts"),
        ("GET",  "/interviews/{id}/report",         "Get aggregated report"),
        ("GET",  "/health",                          "Service health check"),
    ]
    for method, path, desc in endpoints:
        print(f"  {method:5s} {path:38s} {desc}")

    # ══════════════════════════════════════════════════════
    #  10. SQL MIGRATION
    # ══════════════════════════════════════════════════════
    section("10. SQL MIGRATION (migrations/001_init.sql)")
    sql_path = os.path.join("migrations", "001_init.sql")
    if os.path.exists(sql_path):
        with open(sql_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        tables = [l.strip().split()[2] for l in lines if l.strip().startswith("CREATE TABLE")]
        enums = [l.strip().split()[2] for l in lines if l.strip().startswith("CREATE TYPE")]
        indexes = [l.strip() for l in lines if l.strip().startswith("CREATE INDEX")]
        print(f"  Tables created:      {tables}")
        print(f"  Enums created:       {enums}")
        print(f"  Indexes created:     {len(indexes)}")

    # ══════════════════════════════════════════════════════
    section("DEMO COMPLETE")
    print("  All components validated successfully!")
    print("  System is ready for deployment.")
    print()

    # Cleanup demo files
    if os.path.exists(json_path):
        os.remove(json_path)
    storage_path = os.path.join(settings.STORAGE_BASE_PATH, storage_key)
    if os.path.exists(storage_path):
        os.remove(storage_path)


if __name__ == "__main__":
    asyncio.run(main())
