import pytest
from unittest.mock import MagicMock, patch

from app.db.redis import RedisStorage
from app.core.config import RedisConfiguration


@pytest.fixture
def mock_redis_config():
    return RedisConfiguration(url="redis://localhost")


@patch('redis.Redis')
def test_redis_storage_init(mock_redis, mock_redis_config):
    storage = RedisStorage(config=mock_redis_config)
    mock_redis.from_url.assert_called_once_with(mock_redis_config.url)
    assert storage.client is not None


@patch('redis.Redis')
def test_store_value(mock_redis, mock_redis_config):
    mock_client = MagicMock()
    mock_redis.from_url.return_value = mock_client
    storage = RedisStorage(config=mock_redis_config)
    storage.store_value("test_key", "test_value")
    mock_client.set.assert_called_once_with("test_key", "test_value")


@patch('redis.Redis')
def test_get_value(mock_redis, mock_redis_config):
    mock_client = MagicMock()
    mock_redis.from_url.return_value = mock_client
    mock_client.get.return_value = b"test_value"
    storage = RedisStorage(config=mock_redis_config)
    value = storage.get_value("test_key")
    mock_client.get.assert_called_once_with("test_key")
    assert value == "test_value"


@patch('redis.Redis')
def test_get_value_none(mock_redis, mock_redis_config):
    mock_client = MagicMock()
    mock_redis.from_url.return_value = mock_client
    mock_client.get.return_value = None
    storage = RedisStorage(config=mock_redis_config)
    value = storage.get_value("test_key")
    mock_client.get.assert_called_once_with("test_key")
    assert value is None