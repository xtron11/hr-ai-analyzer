# Interview Platform — команды управления

# Сборка только легких сервисов (без ML)
build-infra:
	docker compose build frontend hr

# Сборка audio (долго — ~8-15 мин из-за ML-библиотек)
build-audio:
	docker compose build audio audio_worker

# Полная сборка по очереди (не параллельно — иначе OOM)
build-all:
	docker compose build --no-parallel

# Запуск всей платформы
up:
	docker compose up -d

# Остановка
down:
	docker compose down

# Логи
logs:
	docker compose logs -f

# Загрузить llama3 в Ollama (выполнить после первого запуска)
pull-llm:
	docker exec platform_ollama ollama pull llama3

# Статус сервисов
status:
	docker compose ps

# Полная очистка (удалит все образы и volumes!)
clean:
	docker compose down -v --rmi all
