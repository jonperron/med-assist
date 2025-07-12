# pylint: disable=W0621
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.redis import RedisStorage
from app.core.config import RedisConfiguration


@pytest.fixture
def mock_redis_config():
    return RedisConfiguration(url="redis://localhost")


@patch("app.db.redis.redis.Redis.from_url")
def test_redis_storage_init(mock_from_url, mock_redis_config):
    mock_instance = MagicMock()
    mock_from_url.return_value = mock_instance

    storage = RedisStorage(mock_redis_config)

    mock_from_url.assert_called_once_with(str(mock_redis_config.url))
    assert storage.client == mock_instance


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis")
async def test_store_value(mock_redis, mock_redis_config):
    mock_client = MagicMock()
    mock_client.set = AsyncMock()
    mock_redis.from_url.return_value = mock_client
    storage = RedisStorage(config=mock_redis_config)
    await storage.store_value("test_key", "test_value")
    mock_client.set.assert_called_once_with("test_key", "test_value")


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis")
async def test_get_value(mock_redis, mock_redis_config):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=b"test_value")
    mock_redis.from_url.return_value = mock_client
    storage = RedisStorage(config=mock_redis_config)
    value = await storage.get_value("test_key")
    mock_client.get.assert_called_once_with("test_key")
    assert value == "test_value"


@pytest.mark.asyncio
@patch("app.db.redis.redis.Redis")
async def test_get_value_none(mock_redis, mock_redis_config):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_redis.from_url.return_value = mock_client
    storage = RedisStorage(config=mock_redis_config)
    value = await storage.get_value("test_key")
    mock_client.get.assert_called_once_with("test_key")
    assert value is None
