# --- cache.py ---
# Redis cache layer for ADHDLockIn bandit parameters.

import json
import redis

REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "decode_responses": True
}

_redis = None
_cache_available = False


def init_cache():
    """Connect to Redis. If unavailable, skip cache gracefully."""
    global _redis, _cache_available
    try:
        _redis = redis.Redis(**REDIS_CONFIG)
        _redis.ping()
        _cache_available = True
        print("Cache: Redis initialized successfully.")
    except Exception as e:
        _cache_available = False
        print(f"Cache Warning: Redis unavailable: {e}")


def load_bandit_params_from_cache(user_id='local_user'):
    """Load bandit params from Redis. Returns dict or None."""
    if not _cache_available or not _redis:
        return None
    try:
        data = _redis.get(f"bandit:{user_id}")
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"Cache Warning: Failed to load params: {e}")
        return None


def save_bandit_params_to_cache(params, user_id='local_user'):
    """Save bandit params to Redis with 1 hour expiry."""
    if not _cache_available or not _redis:
        return
    try:
        _redis.setex(f"bandit:{user_id}", 3600, json.dumps(params))
    except Exception as e:
        print(f"Cache Warning: Failed to save params: {e}")


def invalidate_cache(user_id='local_user'):
    """Delete cached bandit params for a user."""
    if not _cache_available or not _redis:
        return
    try:
        _redis.delete(f"bandit:{user_id}")
    except Exception as e:
        print(f"Cache Warning: Failed to invalidate: {e}")


def close_cache():
    """Close the Redis connection."""
    global _redis, _cache_available
    if _redis:
        try:
            _redis.close()
            print("Cache: Connection closed.")
        except Exception as e:
            print(f"Cache Warning: Error closing: {e}")
    _redis = None
    _cache_available = False
