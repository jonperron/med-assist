import redis

from app.core.config import RedisConfiguration

class RedisStorage:
    def __init__(self, config: RedisConfiguration):
        self.config = config
        self.client = redis.Redis.from_url(self.config.url)

    def store_value(self, key: str, value: str):
        """Set a value in Redis."""
        self.client.set(key, value)

    def get_value(self, key: str) -> str:
        """Get a value from Redis."""
        value = self.client.get(key)
        return value.decode('utf-8') if value else None
    