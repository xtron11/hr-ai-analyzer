-- ═══════════════════════════════════════════════════════════
--  Interview Platform — Supabase SQL Migration
--  Выполнить в Supabase SQL Editor
-- ═══════════════════════════════════════════════════════════

-- Включаем расширение для uuid
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Enum'ы ───────────────────────────────────────────────

CREATE TYPE interview_status AS ENUM (
    'pending',
    'in_progress',
    'audio_analyzing',
    'text_analyzing',
    'video_analyzing',
    'aggregating',
    'completed',
    'failed'
);

CREATE TYPE artifact_type AS ENUM (
    'cover_letter',
    'resume',
    'test_task_result',
    'transcript_text',
    'audio_recording',
    'video_frames',
    'auditor_comment',
    'other'
);

CREATE TYPE artifact_direction AS ENUM (
    'input',
    'output'
);

CREATE TYPE storage_provider AS ENUM (
    's3',
    'minio',
    'local_dev'
);

-- ── vacancies ────────────────────────────────────────────

CREATE TABLE vacancies (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title             VARCHAR(255) NOT NULL,
    description       TEXT NULL,                  -- вход #1
    corporate_values  TEXT NULL,                  -- вход #2
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_vacancies_pk ON vacancies (id);

-- ── interviews ───────────────────────────────────────────

CREATE TABLE interviews (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vacancy_id             UUID NOT NULL REFERENCES vacancies(id) ON DELETE CASCADE,
    candidate_external_ref TEXT NULL,
    status                 interview_status NOT NULL DEFAULT 'pending',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_int_status ON interviews (status);
CREATE INDEX idx_int_created_desc ON interviews (created_at DESC);

-- ── files (метаданные, сам файл в Object Storage) ────────

CREATE TABLE files (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    storage_provider storage_provider NOT NULL,
    storage_key      TEXT NOT NULL,               -- path/key в storage
    original_name    TEXT NOT NULL,
    mime_type        VARCHAR(100) NULL,
    size_bytes       BIGINT NULL,
    checksum_sha256  CHAR(64) NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_files_storage_key ON files (storage_key);

-- ── interview_artifacts (привязка файлов к интервью) ─────

CREATE TABLE interview_artifacts (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    interview_id   UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    file_id        UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    artifact_type  artifact_type NOT NULL,
    direction      artifact_direction NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_interview_artifact UNIQUE (interview_id, artifact_type, file_id)
);

CREATE INDEX idx_art_interview ON interview_artifacts (interview_id);
CREATE INDEX idx_art_type ON interview_artifacts (interview_id, artifact_type);

-- ── Триггер для автообновления updated_at ────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_interviews_updated_at
    BEFORE UPDATE ON interviews
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ── RLS (Row Level Security) — опционально ───────────────
-- Раскомментировать если нужно ограничить доступ

-- ALTER TABLE vacancies ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE interviews ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE files ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE interview_artifacts ENABLE ROW LEVEL SECURITY;

-- ═══════════════════════════════════════════════════════════
--  Готово! Таблицы, индексы и enum'ы созданы.
-- ═══════════════════════════════════════════════════════════
