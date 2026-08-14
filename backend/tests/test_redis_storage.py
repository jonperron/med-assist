# pylint: disable=W0621
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.fernet import Fernet

from app.db.encryption import ValueCipher
from app.db.redis import RedisStorage
from app.core.config import RedisConfiguration


@pytest.fixture
def mock_redis_config():
    config = MagicMock(spec=RedisConfiguration)
    config.url = "redis://localhost"
    config.retention_ttl_seconds = 3600
    config.encryption_key = Fernet.generate_key().decode()
    return config


@pytest.fixture
def cipher(mock_redis_config):
    return ValueCipher(mock_redis_config.encryption_key)


@patch("app.db.redis.redis.Redis.from_url")
def test_redis_storage_init(mock_from_url, mock_redis_config):
    mock_instance = MagicMock()
    mock_from_url.return_value = mock_instance

    storage = RedisStorage(mock_redis_config)

    mock_from_url.assert_called_once_with(str(mock_redis_config.url))
    assert storage.client == mock_instance


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis.from_url")
async def test_store_value_applies_configured_retention(
    mock_from_url, mock_redis_config, cipher
):
    mock_client = MagicMock()
    mock_client.set = AsyncMock()
    mock_from_url.return_value = mock_client
    storage = RedisStorage(mock_redis_config, cipher=cipher)

    await storage.store_value("test_key", "test_value")

    key, stored = mock_client.set.call_args.args
    assert key == "test_key"
    assert mock_client.set.call_args.kwargs == {"ex": 3600}
    # The clinical text never reaches Redis in the clear.
    assert stored != "test_value"
    assert cipher.decrypt(stored) == "test_value"


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis.from_url")
async def test_store_value_accepts_explicit_ttl(mock_from_url, mock_redis_config):
    mock_client = MagicMock()
    mock_client.set = AsyncMock()
    mock_from_url.return_value = mock_client
    storage = RedisStorage(mock_redis_config)
    await storage.store_value("test_key", "test_value", ttl_seconds=60)
    assert mock_client.set.call_args.kwargs == {"ex": 60}


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis.from_url")
async def test_get_value_decrypts(mock_from_url, mock_redis_config, cipher):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=cipher.encrypt("test_value").encode())
    mock_from_url.return_value = mock_client
    storage = RedisStorage(mock_redis_config, cipher=cipher)
    value = await storage.get_value("test_key")
    mock_client.get.assert_called_once_with("test_key")
    assert value == "test_value"


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis.from_url")
async def test_get_value_written_under_another_key(mock_from_url, mock_redis_config):
    other_cipher = ValueCipher(Fernet.generate_key().decode())
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=other_cipher.encrypt("secret").encode())
    mock_from_url.return_value = mock_client
    storage = RedisStorage(mock_redis_config)

    assert await storage.get_value("test_key") is None


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis.from_url")
async def test_get_value_none(mock_from_url, mock_redis_config):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_from_url.return_value = mock_client
    storage = RedisStorage(mock_redis_config)
    value = await storage.get_value("test_key")
    mock_client.get.assert_called_once_with("test_key")
    assert value is None


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis.from_url")
async def test_get_ttl(mock_from_url, mock_redis_config):
    mock_client = MagicMock()
    mock_client.ttl = AsyncMock(return_value=42)
    mock_from_url.return_value = mock_client
    storage = RedisStorage(mock_redis_config)
    assert await storage.get_ttl("test_key") == 42
    mock_client.ttl.assert_called_once_with("test_key")


@pytest.mark.asyncio
@pytest.mark.parametrize("redis_ttl", [-1, -2])
@patch("app.db.redis.redis.Redis.from_url")
async def test_get_ttl_missing_or_persistent_key(
    mock_from_url, mock_redis_config, redis_ttl
):
    # Redis answers -2 for a missing key and -1 for a key without an expiry.
    mock_client = MagicMock()
    mock_client.ttl = AsyncMock(return_value=redis_ttl)
    mock_from_url.return_value = mock_client
    storage = RedisStorage(mock_redis_config)
    assert await storage.get_ttl("test_key") is None


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis.from_url")
async def test_delete_value(mock_from_url, mock_redis_config):
    mock_client = MagicMock()
    mock_client.delete = AsyncMock(return_value=1)
    mock_from_url.return_value = mock_client
    storage = RedisStorage(mock_redis_config)
    assert await storage.delete_value("test_key") is True
    mock_client.delete.assert_called_once_with("test_key")


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis.from_url")
async def test_delete_value_multiple_keys(mock_from_url, mock_redis_config):
    mock_client = MagicMock()
    mock_client.delete = AsyncMock(return_value=2)
    mock_from_url.return_value = mock_client
    storage = RedisStorage(mock_redis_config)
    assert await storage.delete_value("a", "b") is True
    mock_client.delete.assert_called_once_with("a", "b")


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis.from_url")
async def test_delete_value_missing_key(mock_from_url, mock_redis_config):
    mock_client = MagicMock()
    mock_client.delete = AsyncMock(return_value=0)
    mock_from_url.return_value = mock_client
    storage = RedisStorage(mock_redis_config)
    assert await storage.delete_value("test_key") is False
