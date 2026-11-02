# Interview Platform — HR AI Analyzer

Платформа автоматического анализа записей собеседований. Загружаешь аудио/видео интервью — система распознаёт речь, оценивает голосовые и эмоциональные характеристики кандидата, а LLM формирует структурированный отчёт для HR.

## Архитектура

```
 frontend (nginx :3000)
        │
        ├──► audio API (:8000) ──► RabbitMQ ──► audio_worker
        │         транскрибация, темп, паузы, питч, эмоции
        │
        └──► hr API (:8001) ─────► RabbitMQ ──► text_worker ──► Ollama (llama3)
                  парсинг ответов, скоринг, отчёт

 Хранилища: MongoDB (результаты ML-анализа), Supabase/PostgreSQL (вакансии, интервью), Redis (кэш)
```

### audio_module — анализ речи
- Транскрибация — **faster-whisper**
- Темп речи, паузы, высота голоса — **praat-parselmouth**
- Акустические признаки — **openSMILE**
- Распознавание эмоций и аффективные измерения — **SpeechBrain** (wav2vec2)
- API: `POST /analyze-audio`, `GET /analysis/{id}`, CRUD вакансий и интервью, `GET /interviews/{id}/report`

### hr-ai-analyzer — анализ текста LLM
- Разбор ответов кандидата, скоринг и отчёт через локальную LLM (**Ollama**, llama3)
- API: `POST /analyze-text`, `GET /analysis/{id}`, `GET /reports`, `GET /reports/{id}`

### frontend
Одностраничный UI на чистом HTML/JS, отдаётся через nginx.

## Запуск

```bash
cp .env.example .env          # строка подключения MongoDB и ключи Supabase
make build-all                # сборка по очереди (ML-образы собираются 8–15 мин)
make up                       # запуск всей платформы
make pull-llm                 # один раз: скачать llama3 в Ollama
```

- UI: http://localhost:3000
- Audio API: http://localhost:8000/docs
- HR API: http://localhost:8001/docs
- RabbitMQ UI: http://localhost:15672

Остальные команды: `make logs`, `make status`, `make down`.

Для локального запуска отдельных модулей без Docker см. `audio_module/.env.example`, `hr-ai-analyzer/.env.example` и `audio_module/run_local.py`. Рекомендуется Python 3.10 (у части C-расширений нет колёс под 3.11+).

## Стек

Python 3.10, FastAPI, RabbitMQ, MongoDB, Supabase (PostgreSQL), Redis, Ollama, faster-whisper, SpeechBrain, openSMILE, Parselmouth, Docker Compose, nginx.
