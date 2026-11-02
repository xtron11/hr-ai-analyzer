# -*- coding: utf-8 -*-
"""
Тест Supabase — вставляет данные во все таблицы платформы.
Запуск: python test_supabase.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import os
from uuid import uuid4
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join("audio_module", ".env"))

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_KEY")  # service_role обходит RLS

from supabase import create_client
db = create_client(URL, KEY)

now = datetime.now(timezone.utc).isoformat()

print("\n" + "=" * 55)
print("  Supabase — тест вставки данных")
print("=" * 55)

# -- 1. vacancies ------------------------------------------
vacancy_id = str(uuid4())
db.table("vacancies").insert({
    "id": vacancy_id,
    "title": "Senior Python Dev — TEST",
    "description": "Тест вставки из кода платформы",
    "corporate_values": "честность, скорость, качество",
    "created_at": now,
}).execute()
print(f"\n✅ vacancies")
print(f"   id:          {vacancy_id}")
print(f"   title:       Senior Python Dev — TEST")

# -- 2. interviews -----------------------------------------
interview_id = str(uuid4())
db.table("interviews").insert({
    "id": interview_id,
    "vacancy_id": vacancy_id,
    "candidate_external_ref": "candidate_demo_42",
    "status": "pending",
    "created_at": now,
    "updated_at": now,
}).execute()
print(f"\n✅ interviews")
print(f"   id:          {interview_id}")
print(f"   vacancy_id:  {vacancy_id}")
print(f"   status:      pending")

# -- 3. files ----------------------------------------------
file_id = str(uuid4())
db.table("files").insert({
    "id": file_id,
    "storage_provider": "local_dev",
    "storage_key": f"interviews/{interview_id}/audio_recording.wav",
    "original_name": "interview_video.mp4",
    "mime_type": "video/mp4",
    "size_bytes": 52428800,          # 50 MB для примера
    "checksum_sha256": "abc123def456" * 4,
    "created_at": now,
}).execute()
print(f"\n✅ files")
print(f"   id:          {file_id}")
print(f"   original:    interview_video.mp4")
print(f"   size:        50 MB")

# -- 4. interview_artifacts --------------------------------
artifact_id = str(uuid4())
db.table("interview_artifacts").insert({
    "id": artifact_id,
    "interview_id": interview_id,
    "file_id": file_id,
    "artifact_type": "audio_recording",
    "direction": "input",
    "created_at": now,
}).execute()
print(f"\n✅ interview_artifacts")
print(f"   id:          {artifact_id}")
print(f"   type:        audio_recording / input")

# -- Читаем обратно ----------------------------------------
print("\n" + "-" * 55)
print("  Проверка — читаем из Supabase:")
print("-" * 55)

v = db.table("vacancies").select("title, created_at").eq("id", vacancy_id).single().execute()
print(f"\n📋 vacancies:  \"{v.data['title']}\"")

i = db.table("interviews").select("status, candidate_external_ref").eq("id", interview_id).single().execute()
print(f"📋 interviews: status={i.data['status']}, ref={i.data['candidate_external_ref']}")

f = db.table("files").select("original_name, size_bytes, mime_type").eq("id", file_id).single().execute()
print(f"📋 files:      {f.data['original_name']} ({f.data['size_bytes']} bytes)")

a = db.table("interview_artifacts").select("artifact_type, direction").eq("id", artifact_id).single().execute()
print(f"📋 artifacts:  {a.data['artifact_type']} / {a.data['direction']}")

print("\n" + "=" * 55)
print("  Данные в Supabase — проверь таблицы в Dashboard!")
print(f"  Vacancy ID:   {vacancy_id}")
print(f"  Interview ID: {interview_id}")
print("=" * 55 + "\n")
