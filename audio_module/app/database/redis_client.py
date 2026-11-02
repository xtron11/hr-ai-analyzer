"""
Redis клиент для кэширования.
Плавная деградация: если Redis недоступен, методы возвращают None.
"""
import json, logging
from typing import Any, Dict, Optional
from app.config import settings

logger = logging.getLogger("redis_cache")

class RedisClient:
    def __init__(self):
        self._client = None
        self._connected = False

    async def connect(self):
        if not settings.redis_enabled:
            logger.warning("Redis URL не задан — без кэша")
            return
        try:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=3)
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
    def is_connected(self): return self._connected

    async def get_cached(self, key: str) -> Optional[Dict]:
        if not self._connected: return None
        try:
            data = await self._client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Redis GET: {e}")
            return None

    async def set_cached(self, key: str, value: Dict, ttl: int = None) -> bool:
        if not self._connected: return False
        try:
            await self._client.setex(key, ttl or settings.REDIS_TTL_SECONDS, json.dumps(value, ensure_ascii=False, default=str))
            return True
        except Exception as e:
            logger.error(f"Redis SET: {e}")
            return False

    async def invalidate(self, key: str) -> bool:
        if not self._connected: return False
        try:
            await self._client.delete(key)
            return True
        except Exception: return False

    @staticmethod
    def audio_key(iid: str): return f"audio_analysis:{iid}"
    @staticmethod
    def report_key(iid: str): return f"report:{iid}"
    @staticmethod
    def interview_key(iid: str): return f"interview:{iid}"

redis_client = RedisClient()
