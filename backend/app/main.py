import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from . import service
from .cache import RemainingCache, Stats, build_client
from .config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("coupon.api")

USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class IssueRequest(BaseModel):
    userId: str

    @field_validator("userId")
    @classmethod
    def valid_user_id(cls, v: str) -> str:
        if not USER_ID_RE.match(v):
            raise ValueError("userId must match [A-Za-z0-9_-]{1,64}")
        return v


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    from psycopg_pool import ConnectionPool

    app.state.pool = ConnectionPool(
        settings.conninfo, min_size=2, max_size=settings.db_pool_max,
        timeout=30, open=True,
    )
    app.state.stats = Stats()
    app.state.cache = RemainingCache(build_client(settings), settings.cache_ttl, app.state.stats)
    yield
    app.state.pool.close()


app = FastAPI(title="coupon-service", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    try:
        with app.state.pool.connection() as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        log.error("healthz failed: %s", exc)
        return JSONResponse({"status": "unhealthy"}, status_code=503)
    return {"status": "ok"}


@app.get("/api/events/{event_id}")
def get_event(event_id: int):
    cache, stats = app.state.cache, app.state.stats
    remaining = cache.get(event_id)
    if remaining is not None:
        return {"eventId": event_id, "remaining": remaining, "source": "cache"}
    try:
        stats.incr("db_read")
        remaining = service.get_remaining(app.state.pool, event_id)
    except service.EventNotFound:
        raise HTTPException(404, "event not found")
    cache.set(event_id, remaining)
    return {"eventId": event_id, "remaining": remaining, "source": "db"}


@app.post("/api/events/{event_id}/issue")
def issue(event_id: int, body: IssueRequest):
    stats = app.state.stats
    try:
        result = service.issue_coupon(app.state.pool, event_id, body.userId)
    except service.EventNotFound:
        raise HTTPException(404, "event not found")
    except service.Duplicate:
        stats.incr("issue_409")
        return JSONResponse({"result": "duplicate", "message": "이미 발급받은 사용자입니다."}, status_code=409)
    except service.SoldOut:
        stats.incr("issue_410")
        return JSONResponse({"result": "sold_out", "message": "쿠폰이 모두 소진되었습니다."}, status_code=410)

    # COMMIT 이후 캐시 무효화. 실패해도 발급 결과에는 영향 없음.
    app.state.cache.invalidate(event_id)
    stats.incr("issue_201")
    return JSONResponse({"result": "issued", **result}, status_code=201)


@app.get("/api/users/{user_id}/coupons")
def user_coupons(user_id: str = Path(pattern=USER_ID_RE.pattern)):
    return {"userId": user_id, "coupons": service.list_coupons(app.state.pool, user_id)}


@app.get("/api/stats")
def get_stats():
    return app.state.stats.snapshot()


@app.post("/api/stats/reset")
def reset_stats():
    app.state.stats.reset()
    return {"status": "reset"}
