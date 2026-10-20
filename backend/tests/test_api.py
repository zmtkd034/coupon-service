import contextlib

import pytest
from fastapi.testclient import TestClient

from app import service
from app.cache import RemainingCache, Stats
from app.main import app


class FakeRedis:
    def __init__(self):
        self.data = {}

    def get(self, k):
        return self.data.get(k)

    def set(self, k, v, ex=None):
        self.data[k] = str(v)

    def delete(self, k):
        self.data.pop(k, None)


class BrokenRedis:
    def get(self, k):
        raise ConnectionError("down")

    set = delete = get


class FakePool:
    @contextlib.contextmanager
    def connection(self):
        class C:
            def execute(self, *a, **k):
                return self
        yield C()


@pytest.fixture
def client(monkeypatch):
    stats = Stats()
    app.state.pool = FakePool()
    app.state.stats = stats
    app.state.redis = FakeRedis()
    app.state.cache = RemainingCache(app.state.redis, 3, stats)
    return TestClient(app)  # lifespan 미실행: DB/Redis 없이 테스트


def test_healthz(client):
    assert client.get("/healthz").status_code == 200


def test_event_cache_miss_then_hit(client, monkeypatch):
    monkeypatch.setattr(service, "get_remaining", lambda pool, eid: 100)
    assert client.get("/api/events/1").json()["source"] == "db"
    assert client.get("/api/events/1").json() == {"eventId": 1, "remaining": 100, "source": "cache"}
    assert app.state.stats.snapshot()["cache_hit"] == 1


def test_event_falls_back_to_db_when_redis_down(client, monkeypatch):
    app.state.cache = RemainingCache(BrokenRedis(), 3, app.state.stats)
    monkeypatch.setattr(service, "get_remaining", lambda pool, eid: 7)
    r = client.get("/api/events/1")
    assert r.status_code == 200 and r.json()["remaining"] == 7


def test_event_not_found(client, monkeypatch):
    def boom(pool, eid):
        raise service.EventNotFound(eid)
    monkeypatch.setattr(service, "get_remaining", boom)
    assert client.get("/api/events/99").status_code == 404


def test_issue_201_invalidates_cache(client, monkeypatch):
    app.state.redis.data["coupon:1:remaining"] = "5"
    monkeypatch.setattr(service, "issue_coupon", lambda p, e, u: {"couponId": 1, "eventId": e,
                        "userId": u, "issuedAt": "t", "remaining": 4})
    r = client.post("/api/events/1/issue", json={"userId": "user-1"})
    assert r.status_code == 201
    assert "coupon:1:remaining" not in app.state.redis.data


@pytest.mark.parametrize("exc,code", [(service.Duplicate, 409), (service.SoldOut, 410)])
def test_issue_error_codes(client, monkeypatch, exc, code):
    def boom(p, e, u):
        raise exc()
    monkeypatch.setattr(service, "issue_coupon", boom)
    assert client.post("/api/events/1/issue", json={"userId": "u1"}).status_code == code


@pytest.mark.parametrize("uid", ["", "a b", "x" * 65, "<script>"])
def test_issue_rejects_bad_user_id(client, uid):
    assert client.post("/api/events/1/issue", json={"userId": uid}).status_code == 422


def test_cache_disabled_never_touches_redis(client, monkeypatch):
    app.state.cache = RemainingCache(None, 3, app.state.stats)
    monkeypatch.setattr(service, "get_remaining", lambda p, e: 3)
    assert client.get("/api/events/1").json()["source"] == "db"
    assert app.state.stats.snapshot()["cache_miss"] == 0
