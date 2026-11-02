"""Redis кэш для hr-ai-analyzer."""
import json, logging
from typing import Any, Dict, Optional
from app.config import settings

logger = logging.getLogger("hr.redis")


class RedisClient:
    def __init__(self):
        self._client = None
        self._connected = False

    async def connect(self):
        try:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(
                settings.REDIS_URL, decode_responses=True, socket_connect_timeout=3
            )
            await self._client.ping()
            self._connected = True
            logger.info(f"Redis подключен: {settings.REDIS_URL}")
        except Exception as e:
            logger.error(f"Redis недоступен: {e}")
            self._connected = False

    async def disconnect(self):
        if self._client:
            await self._client.close()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def get_cached(self, key: str) -> Optional[Dict]:
        if not self._connected:
            return None
        try:
            data = await self._client.get(key)
            return json.loads(data) if data else None
        except Exception:
            return None

    async def set_cached(self, key: str, value: Dict, ttl: int = None) -> bool:
        if not self._connected:
            return False
        try:
            await self._client.setex(
                key,
                ttl or settings.REDIS_TTL_SECONDS,
                json.dumps(value, ensure_ascii=False, default=str),
            )
            return True
        except Exception:
            return False

    @staticmethod
    def text_key(iid: str): return f"text_analysis:{iid}"

    @staticmethod
    def report_key(iid: str): return f"report:{iid}"


redis_client = RedisClient()
