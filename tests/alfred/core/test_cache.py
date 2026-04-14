from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from alfred.core.cache import cache_get, cache_set, cache_invalidate


class TestCacheGet:
    def test_returns_cached_value(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({"items": [1, 2, 3]})
        with patch("alfred.core.cache.get_redis_client", return_value=mock_redis):
            result = cache_get("test:key")
        assert result == {"items": [1, 2, 3]}

    def test_returns_none_on_miss(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        with patch("alfred.core.cache.get_redis_client", return_value=mock_redis):
            result = cache_get("test:key")
        assert result is None

    def test_returns_none_when_redis_unavailable(self):
        with patch("alfred.core.cache.get_redis_client", return_value=None):
            result = cache_get("test:key")
        assert result is None

    def test_returns_none_on_redis_error(self):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = ConnectionError("Redis down")
        with patch("alfred.core.cache.get_redis_client", return_value=mock_redis):
            result = cache_get("test:key")
        assert result is None


class TestCacheSet:
    def test_stores_value_with_ttl(self):
        mock_redis = MagicMock()
        with patch("alfred.core.cache.get_redis_client", return_value=mock_redis):
            cache_set("test:key", {"data": "value"}, ttl=60)
        mock_redis.set.assert_called_once_with(
            "test:key", json.dumps({"data": "value"}), ex=60
        )

    def test_silent_on_redis_unavailable(self):
        with patch("alfred.core.cache.get_redis_client", return_value=None):
            cache_set("test:key", {"data": "value"})


class TestCacheInvalidate:
    def test_deletes_matching_keys(self):
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = ["prefix:a", "prefix:b"]
        with patch("alfred.core.cache.get_redis_client", return_value=mock_redis):
            cache_invalidate("prefix:")
        assert mock_redis.delete.call_count == 2

    def test_silent_on_redis_unavailable(self):
        with patch("alfred.core.cache.get_redis_client", return_value=None):
            cache_invalidate("prefix:")
