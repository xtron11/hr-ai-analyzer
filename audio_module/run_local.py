"""
Локальный запуск audio_module БЕЗ Docker и БЕЗ ML-зависимостей.

ML-сервисы (torch / whisper / speechbrain) заменены реалистичными заглушками.
MongoDB Atlas, Redis, RabbitMQ — настоящие соединения из .env.

Запуск:
    E:\\praktika\\venv_local\\Scripts\\python.exe run_local.py

Затем открой:
    http://localhost:8000/docs      — Swagger UI
    http://localhost:8000/health    — статус сервисов

Тест через curl (PowerShell):
    Invoke-RestMethod -Uri http://localhost:8000/analyze-audio `
        -Method POST `
        -Form @{ file = Get-Item "C:\\path\\to\\video.mp4" }
"""

import sys
import os
import types
import random
import math

# ─────────────────────────────────────────────────────────────
#  Добавляем audio_module в path
# ─────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


import numpy as np


# ─────────────────────────────────────────────────────────────
#  Заглушки для ML-модулей (torch / torchaudio / speechbrain /
#  transformers / whisper / silero-vad / opensmile)
# ─────────────────────────────────────────────────────────────

def _make_stub(name):
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m

for _mod in [
    "torch", "torch.nn", "torch.nn.functional",
    "torchaudio", "torchaudio.transforms", "torchaudio.functional",
    "speechbrain", "speechbrain.inference",
    "speechbrain.inference.classifiers",
    "transformers",
    "faster_whisper",
    "silero_vad",
    "opensmile",
    "parselmouth",
    "hyperpyyaml",
    "huggingface_hub",
]:
    _make_stub(_mod)


# ─────────────────────────────────────────────────────────────
#  Заглушка AudioPreprocessor
# ─────────────────────────────────────────────────────────────

class _FakePreprocessor:
    def process(self, audio_path: str):
        size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 100_000
        duration = max(5.0, size / 32000)
        sr = 16000
        n = int(duration * sr)
        waveform = [math.sin(2 * math.pi * 220 * i / sr) * 0.3 for i in range(min(n, sr * 10))]
        import numpy as np
        return np.array(waveform, dtype="float32"), sr, round(duration, 2)

_fake_prep = _FakePreprocessor()

# Подменяем модуль до импорта main
_prep_mod = types.ModuleType("app.services.audio_preprocessor")
_prep_mod.audio_preprocessor = _fake_prep
_prep_mod.AudioPreprocessor = _FakePreprocessor
sys.modules["app.services.audio_preprocessor"] = _prep_mod


# ─────────────────────────────────────────────────────────────
#  Заглушка SpeechRateService (Whisper)
# ─────────────────────────────────────────────────────────────

class _FakeSpeechRate:
    def analyze(self, waveform, sample_rate, duration_sec):
        wpm = round(random.uniform(90, 160), 1)
        words = int(wpm * duration_sec / 60)
        return {
            "speech_rate_wpm": wpm,
            "speech_rate_method": "mock_asr",
            "word_count": words,
            "detected_language": "ru",
            "transcript_segments": [
                {"start": 0.0, "end": duration_sec / 3,
                 "text": "Добрый день, рад познакомиться."},
                {"start": duration_sec / 3, "end": 2 * duration_sec / 3,
                 "text": "Расскажу о своём опыте работы."},
                {"start": 2 * duration_sec / 3, "end": duration_sec,
                 "text": "Работал три года разработчиком."},
            ],
        }

_sr_mod = types.ModuleType("app.services.speech_rate_service")
_sr_mod.speech_rate_service = _FakeSpeechRate()
sys.modules["app.services.speech_rate_service"] = _sr_mod


# ─────────────────────────────────────────────────────────────
#  Заглушка SpeechPausesService (silero-vad)
# ─────────────────────────────────────────────────────────────

class _FakePauses:
    def analyze(self, waveform, sample_rate, duration_sec):
        n = random.randint(3, 12)
        return {
            "total_pauses": n,
            "total_pause_time_sec": round(n * random.uniform(1.0, 2.5), 2),
            "avg_pause_duration_sec": round(random.uniform(1.2, 2.0), 2),
            "long_pauses_count": random.randint(0, 3),
            "pause_rate_per_min": round(n / (duration_sec / 60), 2),
            "pause_threshold_sec": 1.5,
        }

_p_mod = types.ModuleType("app.services.speech_pauses_service")
_p_mod.speech_pauses_service = _FakePauses()
sys.modules["app.services.speech_pauses_service"] = _p_mod


# ─────────────────────────────────────────────────────────────
#  Заглушка SpeechPitchService (parselmouth)
# ─────────────────────────────────────────────────────────────

class _FakePitch:
    def analyze(self, waveform, sample_rate):
        avg = round(random.uniform(120, 250), 1)
        return {
            "avg_pitch": avg,
            "min_pitch": round(avg * 0.6, 1),
            "max_pitch": round(avg * 1.7, 1),
            "std_pitch": round(random.uniform(20, 70), 1),
            "pitch_range": round(avg * 1.1, 1),
            "voiced_ratio": round(random.uniform(0.55, 0.85), 2),
        }

_pit_mod = types.ModuleType("app.services.speech_pitch_service")
_pit_mod.speech_pitch_service = _FakePitch()
sys.modules["app.services.speech_pitch_service"] = _pit_mod


# ─────────────────────────────────────────────────────────────
#  Заглушка EmotionRecognitionService (speechbrain)
# ─────────────────────────────────────────────────────────────

EMOTIONS = ["neutral", "happy", "fear", "angry", "disgust", "sad"]

class _FakeEmotion:
    def analyze_file(self, file_path):
        emo = random.choice(EMOTIONS)
        conf = round(random.uniform(0.55, 0.90), 2)
        return {
            "emotion": emo,
            "confidence": conf,
            "emotions_timeline": [
                {"start_sec": 0.0,   "end_sec": 10.0, "emotion": emo,    "confidence": conf},
                {"start_sec": 10.0,  "end_sec": 25.0, "emotion": "neutral", "confidence": 0.72},
                {"start_sec": 25.0,  "end_sec": 40.0, "emotion": emo,    "confidence": round(conf * 0.9, 2)},
            ],
        }

_emo_mod = types.ModuleType("app.services.emotion_recognition_service")
_emo_mod.emotion_recognition_service = _FakeEmotion()
sys.modules["app.services.emotion_recognition_service"] = _emo_mod


# ─────────────────────────────────────────────────────────────
#  Заглушка AffectDimensionsService
# ─────────────────────────────────────────────────────────────

class _FakeAffect:
    def analyze(self, waveform, sample_rate, duration_sec,
                segment_sec=5.0, hop_sec=5.0):
        return {
            "valence":    round(random.uniform(0.3, 0.8), 2),
            "arousal":    round(random.uniform(0.3, 0.8), 2),
            "dominance":  round(random.uniform(0.3, 0.7), 2),
        }

_aff_mod = types.ModuleType("app.services.affect_dimensions_service")
_aff_mod.affect_dimensions_service = _FakeAffect()
sys.modules["app.services.affect_dimensions_service"] = _aff_mod


# ─────────────────────────────────────────────────────────────
#  Заглушка OpenSmileService
# ─────────────────────────────────────────────────────────────

class _FakeOpenSmile:
    def analyze(self, waveform, sample_rate, duration_sec,
                segment_sec=5.0, hop_sec=5.0):
        return {
            "mfcc_mean": [round(random.gauss(0, 10), 2) for _ in range(13)],
            "rms_energy": round(random.uniform(0.01, 0.08), 4),
            "zcr_mean": round(random.uniform(0.05, 0.15), 4),
            "spectral_centroid": round(random.uniform(1000, 3000), 1),
        }

_osm_mod = types.ModuleType("app.services.opensmile_service")
_osm_mod.opensmile_service = _FakeOpenSmile()
sys.modules["app.services.opensmile_service"] = _osm_mod


# ─────────────────────────────────────────────────────────────
#  Заглушка ComplexEmotionService
# ─────────────────────────────────────────────────────────────

class _FakeComplex:
    def analyze(self, transcript_segments, duration_sec,
                speech_rate_wpm=None, pitch_metrics=None,
                affect_dimensions=None, opensmile_features=None,
                segment_sec=5.0, hop_sec=5.0):
        return {
            "confidence_level": random.choice(["low", "medium", "high"]),
            "stress_level":     random.choice(["low", "medium", "high"]),
            "engagement":       round(random.uniform(0.4, 0.9), 2),
        }

_cx_mod = types.ModuleType("app.services.complex_emotion_service")
_cx_mod.complex_emotion_service = _FakeComplex()
sys.modules["app.services.complex_emotion_service"] = _cx_mod


# ─────────────────────────────────────────────────────────────
#  Патч extract_audio_from_video: без ffmpeg просто копируем файл
# ─────────────────────────────────────────────────────────────

import shutil

def _fake_extract_audio(video_path: str) -> str:
    """Если нет ffmpeg — просто отдаём тот же файл как 'wav'."""
    import subprocess
    wav_path = video_path + "_extracted.wav"
    cmd = [
        "ffmpeg", "-i", video_path, "-vn",
        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        wav_path, "-y", "-loglevel", "error",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return wav_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        # ffmpeg недоступен — копируем как есть
        shutil.copy2(video_path, wav_path)
        return wav_path


# ─────────────────────────────────────────────────────────────
#  Импортируем и патчим main
# ─────────────────────────────────────────────────────────────

import app.main as _main_module
_main_module.extract_audio_from_video = _fake_extract_audio

app_instance = _main_module.app


# ─────────────────────────────────────────────────────────────
#  Запуск
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("  audio_module — локальный запуск (без Docker / без ML)")
    print("=" * 60)
    print("  Swagger UI: http://localhost:8000/docs")
    print("  Health:     http://localhost:8000/health")
    print()
    print("  Тест через PowerShell:")
    print('  Invoke-RestMethod -Uri http://localhost:8000/analyze-audio \\')
    print('    -Method POST \\')
    print('    -Form @{ file = Get-Item "C:\\path\\to\\your_video.mp4" }')
    print("=" * 60)

    uvicorn.run(
        "run_local:app_instance",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
