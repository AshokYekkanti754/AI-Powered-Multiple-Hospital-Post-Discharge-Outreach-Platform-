"""Atomic, tenant-isolated concurrency semaphore with a test fallback."""
from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager

from app.core.config import settings


class InMemorySemaphore:
    def __init__(self):
        self._lock = threading.Lock()
        self._slots: dict[str, dict[str, float]] = {}

    @contextmanager
    def acquire(self, hospital_id: str, capacity: int, ttl: int = 30):
        key = str(hospital_id)
        token = str(uuid.uuid4())
        with self._lock:
            slots = self._slots.setdefault(key, {})
            now = time.monotonic()
            for stale in [item for item, expires in slots.items() if expires <= now]:
                slots.pop(stale, None)
            if len(slots) >= capacity:
                yield False
                return
            slots[token] = now + ttl
        try:
            yield True
        finally:
            with self._lock:
                self._slots.get(key, {}).pop(token, None)

    def active_count(self, hospital_id: str) -> int:
        with self._lock:
            slots = self._slots.get(str(hospital_id), {})
            now = time.monotonic()
            for stale in [item for item, expires in slots.items() if expires <= now]:
                slots.pop(stale, None)
            return len(slots)

    def release_any(self, hospital_id: str, count: int = 1) -> int:
        """Release `count` slots without knowing their tokens (stuck-task reclaimer)."""
        released = 0
        with self._lock:
            slots = self._slots.get(str(hospital_id), {})
            for _ in range(count):
                if slots:
                    # Pop one arbitrary token (dicts preserve insertion order).
                    slots.pop(next(iter(slots)))
                    released += 1
        return released


class RedisSemaphore:
    def __init__(self, client):
        self.client = client
        self._acquire = client.register_script("""
            local now = redis.call('TIME')[1]
            redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
            if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
            redis.call('ZADD', KEYS[1], now + tonumber(ARGV[2]), ARGV[3])
            redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
            return 1
        """)
        self._release = client.register_script("redis.call('ZREM', KEYS[1], ARGV[1]); return 1")

    @staticmethod
    def key(hospital_id: str) -> str:
        return f"lock:concurrency:{hospital_id}"

    @contextmanager
    def acquire(self, hospital_id: str, capacity: int, ttl: int = 30):
        token = str(uuid.uuid4())
        key = self.key(str(hospital_id))
        acquired = bool(self._acquire(keys=[key], args=[capacity, ttl, token]))
        try:
            yield acquired
        finally:
            if acquired:
                self._release(keys=[key], args=[token])

    def active_count(self, hospital_id: str) -> int:
        return int(self.client.zcard(self.key(str(hospital_id))))

    def release_any(self, hospital_id: str, count: int = 1) -> int:
        """Release `count` slots by removing the oldest-held tokens from the zset."""
        key = self.key(str(hospital_id))
        for _ in range(count):
            self.client.zremrangebyrank(key, 0, 0)
        return count


def _build_semaphore():
    try:
        import redis
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        client.ping()
        return RedisSemaphore(client)
    except Exception:
        return InMemorySemaphore()


semaphore = _build_semaphore()
