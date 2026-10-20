"""재고 조회 캐시. 장애 시에도 예외를 밖으로 내지 않고 DB 조회로 대체하게 한다."""
import logging
import threading
from typing import Optional

log = logging.getLogger("coupon.cache")


class Stats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counters = {"cache_hit": 0, "cache_miss": 0, "cache_error": 0,
                         "db_read": 0, "issue_201": 0, "issue_409": 0, "issue_410": 0}

    def incr(self, key: str) -> None:
        with self._lock:
            self.counters[key] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.counters)

    def reset(self) -> None:
        with self._lock:
            for k in self.counters:
                self.counters[k] = 0


def remaining_key(event_id: int) -> str:
    return f"coupon:{event_id}:remaining"


class RemainingCache:
    def __init__(self, client, ttl: int, stats: Stats) -> None:
        self.client = client  # None 이면 캐시 비활성
        self.ttl = ttl
        self.stats = stats

    def get(self, event_id: int) -> Optional[int]:
        if self.client is None:
            return None
        try:
            val = self.client.get(remaining_key(event_id))
        except Exception as exc:
            self.stats.incr("cache_error")
            log.warning("redis get failed: %s", exc)
            return None
        if val is None:
            self.stats.incr("cache_miss")
            return None
        self.stats.incr("cache_hit")
        return int(val)

    def set(self, event_id: int, remaining: int) -> None:
        if self.client is None:
            return
        try:
            self.client.set(remaining_key(event_id), remaining, ex=self.ttl)
        except Exception as exc:
            self.stats.incr("cache_error")
            log.warning("redis set failed: %s", exc)

    def invalidate(self, event_id: int) -> None:
        if self.client is None:
            return
        try:
            self.client.delete(remaining_key(event_id))
        except Exception as exc:
            self.stats.incr("cache_error")
            log.warning("redis delete failed: %s", exc)


def build_client(settings):
    if not settings.cache_enabled:
        return None
    import redis

    return redis.Redis(
        host=settings.redis_host, port=settings.redis_port, ssl=settings.redis_tls,
        socket_connect_timeout=1, socket_timeout=1, decode_responses=True,
    )
