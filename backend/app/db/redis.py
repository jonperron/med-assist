import redis.asyncio as redis

from app.core.config import RedisConfiguration
from app.db.encryption import ValueCipher


class RedisStorage:
    def __init__(self, config: RedisConfiguration, cipher: ValueCipher | None = None):
        self.config = config
        self.client = redis.Redis.from_url(str(self.config.url))
        # Every value is encrypted here rather than at the call sites, so no
        # caller can accidentally write clinical text in the clear.
        self.cipher = cipher or ValueCipher(config.encryption_key)

    async def store_value(self, key: str, value: str, ttl_seconds: int | None = None):
        """Set an encrypted value in Redis. Every key expires, so nothing is retained forever."""
        await self.client.set(
            key,
            self.cipher.encrypt(value),
            ex=ttl_seconds or self.config.retention_ttl_seconds,
        )

    async def get_value(self, key: str) -> str | None:
        """Get a value from Redis, decrypted. None when missing or unreadable."""
        value = await self.client.get(key)
        if not value:
            return None
        return self.cipher.decrypt(value.decode("utf-8"))

    async def get_ttl(self, key: str) -> int | None:
        """Seconds left before the key expires, or None if it is missing or persistent."""
        ttl = await self.client.ttl(key)
        return ttl if ttl > 0 else None

    async def delete_value(self, *keys: str) -> bool:
        """Delete one or more keys. True when at least one key was removed."""
        if not keys:
            return False
        return bool(await self.client.delete(*keys))
