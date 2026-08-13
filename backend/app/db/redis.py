import redis.asyncio as redis

from app.core.config import RedisConfiguration


class RedisStorage:
    def __init__(self, config: RedisConfiguration):
        self.config = config
        self.client = redis.Redis.from_url(str(self.config.url))

    async def store_value(self, key: str, value: str, ttl_seconds: int | None = None):
        """Set a value in Redis. Every key expires, so nothing is retained forever."""
        await self.client.set(
            key, value, ex=ttl_seconds or self.config.retention_ttl_seconds
        )

    async def get_value(self, key: str) -> str | None:
        """Get a value from Redis."""
        value = await self.client.get(key)
        return value.decode("utf-8") if value else None

    async def get_ttl(self, key: str) -> int | None:
        """Seconds left before the key expires, or None if it is missing or persistent."""
        ttl = await self.client.ttl(key)
        return ttl if ttl > 0 else None

    async def delete_value(self, key: str) -> bool:
        """Delete a key. True when a key was actually removed."""
        return bool(await self.client.delete(key))
