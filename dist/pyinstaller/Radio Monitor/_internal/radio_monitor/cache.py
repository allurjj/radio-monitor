"""
Simple caching system for frequently accessed data

Provides thread-safe in-memory caching with TTL (time-to-live) support
for database query results and expensive computations.
"""

import threading
import time
import logging
from typing import Any, Callable, Optional, Dict, Tuple
from functools import wraps

logger = logging.getLogger(__name__)


class CacheEntry:
    """A single cache entry with value and expiration"""

    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.expires_at = time.time() + ttl

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return time.time() > self.expires_at


class SimpleCache:
    """Thread-safe in-memory cache with TTL support"""

    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats['misses'] += 1
                return None

            if entry.is_expired():
                # Remove expired entry
                del self._cache[key]
                self._stats['evictions'] += 1
                self._stats['misses'] += 1
                return None

            self._stats['hits'] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache with TTL

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (default: 300 = 5 minutes)
        """
        with self._lock:
            self._cache[key] = CacheEntry(value, ttl)

    def delete(self, key: str) -> bool:
        """Delete entry from cache

        Args:
            key: Cache key

        Returns:
            True if entry was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()

    def cleanup_expired(self) -> int:
        """Remove all expired entries

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
                self._stats['evictions'] += 1
            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics

        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (
                self._stats['hits'] / total_requests * 100
                if total_requests > 0
                else 0
            )

            return {
                'size': len(self._cache),
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'evictions': self._stats['evictions'],
                'hit_rate': f'{hit_rate:.1f}%'
            }

    def reset_stats(self) -> None:
        """Reset cache statistics"""
        with self._lock:
            self._stats = {
                'hits': 0,
                'misses': 0,
                'evictions': 0
            }


# Global cache instance
_cache = SimpleCache()


def get_cache() -> SimpleCache:
    """Get the global cache instance"""
    return _cache


def cached(ttl: int = 300, key_func: Optional[Callable] = None):
    """Decorator to cache function results

    Args:
        ttl: Time-to-live in seconds (default: 300)
        key_func: Optional function to generate cache key from args

    Example:
        @cached(ttl=600)
        def get_system_status():
            return expensive_database_query()

        @cached(ttl=300, key_func=lambda user_id: f'user_{user_id}')
        def get_user_data(user_id):
            return fetch_user(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key: function name + args
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

            # Try to get from cache
            cached_value = _cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Cache miss - call function
            logger.debug(f"Cache miss: {cache_key}")
            result = func(*args, **kwargs)

            # Store in cache
            _cache.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


def cache_key(*parts) -> str:
    """Generate a cache key from parts

    Args:
        *parts: Parts to join into cache key

    Returns:
        Cache key string
    """
    return ":".join(str(part) for part in parts)


def invalidate_pattern(pattern: str) -> int:
    """Invalidate all cache entries matching a pattern

    Args:
        pattern: Pattern to match (supports simple * wildcard)

    Returns:
        Number of entries invalidated
    """
    import re
    with _cache._lock:
        # Convert glob pattern to regex
        regex_pattern = pattern.replace('*', '.*')
        regex = re.compile(f'^{regex_pattern}$')

        keys_to_delete = [
            key for key in _cache._cache.keys()
            if regex.match(key)
        ]

        for key in keys_to_delete:
            del _cache._cache[key]

        return len(keys_to_delete)


# Cache TTL constants (in seconds)
CACHE_TTL = {
    'very_short': 60,      # 1 minute
    'short': 300,          # 5 minutes
    'medium': 600,         # 10 minutes
    'long': 1800,          # 30 minutes
    'very_long': 3600      # 1 hour
}
