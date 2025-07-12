import redis

from app.core.config import RedisConfiguration

class RedisStorage:
    def __init__(self, config: RedisConfiguration):
        self.config = config
        self.client = redis.Redis.from_url(self.config.url)

    async def store_value(self, key: str, value: str):
        """Set a value in Redis."""
        await self.client.set(key, value)

    async def get_value(self, key: str) -> str:
        """Get a value from Redis."""
        value = await self.client.get(key)
        return value.decode('utf-8') if value else None
    