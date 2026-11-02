"""RabbitMQ consumer для очереди text_analysis_queue."""
import json, logging
from typing import Callable
from app.config import settings

logger = logging.getLogger("hr.rabbitmq")


class RabbitMQClient:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._connected = False

    async def connect(self):
        try:
            import aio_pika
            self._connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL, timeout=5
            )
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=settings.WORKER_PREFETCH_COUNT)
            await self._channel.declare_queue(settings.TEXT_QUEUE_NAME, durable=True)
            self._connected = True
            logger.info(f"RabbitMQ подключен, очередь: {settings.TEXT_QUEUE_NAME}")
        except Exception as e:
            logger.error(f"RabbitMQ недоступен: {e}")
            self._connected = False

    async def disconnect(self):
        if self._connection:
            await self._connection.close()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def consume(self, queue_name: str, callback: Callable) -> None:
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
