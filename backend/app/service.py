"""PostgreSQL 기반 발급 로직. 발급 성공 여부는 DB COMMIT 으로만 결정한다."""
from psycopg import errors


class EventNotFound(Exception):
    pass


class Duplicate(Exception):
    pass


class SoldOut(Exception):
    pass


def get_remaining(pool, event_id: int) -> int:
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT remaining_qty FROM events WHERE id = %s", (event_id,)
        ).fetchone()
    if row is None:
        raise EventNotFound(event_id)
    return row[0]


def issue_coupon(pool, event_id: int, user_id: str) -> dict:
    try:
        # 예외 발생 시 컨텍스트가 ROLLBACK, 정상 종료 시 COMMIT 한다.
        with pool.connection() as conn:
            # 이벤트 행 잠금: 재고 판단을 직렬화
            row = conn.execute(
                "SELECT remaining_qty FROM events WHERE id = %s FOR UPDATE", (event_id,)
            ).fetchone()
            if row is None:
                raise EventNotFound(event_id)

            dup = conn.execute(
                "SELECT 1 FROM coupon_issues WHERE event_id = %s AND user_id = %s",
                (event_id, user_id),
            ).fetchone()
            if dup:
                raise Duplicate(user_id)

            if row[0] <= 0:
                raise SoldOut(event_id)

            conn.execute(
                "UPDATE events SET remaining_qty = remaining_qty - 1 WHERE id = %s",
                (event_id,),
            )
            issued = conn.execute(
                "INSERT INTO coupon_issues (event_id, user_id) VALUES (%s, %s) "
                "RETURNING id, issued_at",
                (event_id, user_id),
            ).fetchone()
    except errors.UniqueViolation:
        # UNIQUE(event_id, user_id) 로 중복을 한 번 더 차단
        raise Duplicate(user_id)

    return {"couponId": issued[0], "eventId": event_id, "userId": user_id,
            "issuedAt": issued[1].isoformat(), "remaining": row[0] - 1}


def list_coupons(pool, user_id: str) -> list:
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT id, event_id, issued_at FROM coupon_issues "
            "WHERE user_id = %s ORDER BY id",
            (user_id,),
        ).fetchall()
    return [{"couponId": r[0], "eventId": r[1], "issuedAt": r[2].isoformat()} for r in rows]
