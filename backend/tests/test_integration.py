"""실제 PostgreSQL 이 있을 때만 실행: TEST_DATABASE_URL=postgresql://user:pw@host/db pytest"""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import service

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")

SCHEMA = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "schema.sql")


@pytest.fixture
def pool():
    from psycopg_pool import ConnectionPool

    p = ConnectionPool(URL, min_size=2, max_size=30, open=True)
    with p.connection() as c:
        c.execute(open(SCHEMA).read())
        c.execute("TRUNCATE coupon_issues RESTART IDENTITY")
        c.execute("DELETE FROM events")
        c.execute("INSERT INTO events (id, name, total_qty, remaining_qty) VALUES (1,'t',100,100)")
    yield p
    p.close()


def _try(pool, uid):
    try:
        service.issue_coupon(pool, 1, uid)
        return 201
    except service.Duplicate:
        return 409
    except service.SoldOut:
        return 410


def test_duplicate_user_100_concurrent(pool):
    with ThreadPoolExecutor(30) as ex:
        codes = list(ex.map(lambda _: _try(pool, "same"), range(100)))
    assert codes.count(201) == 1 and codes.count(409) == 99


def test_sold_out_500_users(pool):
    with ThreadPoolExecutor(30) as ex:
        codes = list(ex.map(lambda i: _try(pool, f"u{i}"), range(500)))
    assert codes.count(201) == 100 and codes.count(410) == 400
    assert service.get_remaining(pool, 1) == 0
