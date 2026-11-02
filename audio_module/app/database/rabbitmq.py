"""
RabbitMQ клиент для очередей задач.
Использует aio-pika для async AMQP.
Плавная деградация: без RabbitMQ задачи выполняются синхронно.
"""
import json, logging
from typing import Any, Callable, Dict, Optional
from app.config import settings

logger = logging.getLogger("rabbitmq")

class RabbitMQClient:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._connected = False

    async def connect(self):
        if not settings.rabbitmq_enabled:
            logger.warning("RabbitMQ URL не задан — задачи выполняются синхронно")
            return
        try:
            import aio_pika
            self._connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL, timeout=5
            )
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=settings.WORKER_PREFETCH_COUNT)
            # Объявляем очереди
            await self._channel.declare_queue(settings.AUDIO_QUEUE_NAME, durable=True)
            await self._channel.declare_queue(settings.TEXT_QUEUE_NAME, durable=True)
            self._connected = True
            logger.info(f"RabbitMQ подключен, очереди: {settings.AUDIO_QUEUE_NAME}, {settings.TEXT_QUEUE_NAME}")
        except Exception as e:
            logger.error(f"RabbitMQ недоступен: {e}")
            self._connected = False

    async def disconnect(self):
        if self._connection:
            await self._connection.close()
            self._connected = False

    @property
    def is_connected(self): return self._connected

    async def publish_task(self, queue_name: str, payload: Dict[str, Any]) -> bool:
        """Опубликовать задачу в очередь."""
        if not self._connected:
            logger.warning(f"RabbitMQ не подключен — задача для {queue_name} не отправлена")
            return False
        try:
            import aio_pika
            body = json.dumps(payload, ensure_ascii=False, default=str).encode()
            message = aio_pika.Message(
                body=body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            )
            await self._channel.default_exchange.publish(
                message, routing_key=queue_name
            )
            logger.info(f"Задача опубликована в {queue_name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка публикации в {queue_name}: {e}")
            return False

    async def publish_audio_task(self, interview_id: str, file_path: str) -> bool:
        """Опубликовать задачу аудио-анализа."""
        return await self.publish_task(
            settings.AUDIO_QUEUE_NAME,
            {"interview_id": interview_id, "file_path": file_path, "task": "audio_analysis"},
        )

    async def publish_text_task(
        self,
        interview_id: str,
        transcript_segments: list,
        transcript_text: str = "",
        vacancy_id: str = None,
        detected_language: str = "unknown",
    ) -> bool:
        """Опубликовать задачу текстового/LLM-анализа."""
        return await self.publish_task(
            settings.TEXT_QUEUE_NAME,
            {
                "task": "text_analysis",
                "interview_id": interview_id,
                "transcript_segments": transcript_segments,
                "transcript_text": transcript_text,
                "vacancy_id": vacancy_id,
                "detected_language": detected_language,
                "vacancy": {},
            },
        )

    async def consume(self, queue_name: str, callback: Callable) -> None:
        """Подписаться на очередь и вызывать callback для каждого сообщения."""
        if not self._connected:
            logger.error("RabbitMQ не подключен — consume невозможен")
            return
        try:
            queue = await self._channel.declare_queue(queue_name, durable=True)
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        payload = json.loads(message.body.decode())
                        await callback(payload)
        except Exception as e:
            logger.error(f"Ошибка consume {queue_name}: {e}")

rabbitmq_client = RabbitMQClient()
