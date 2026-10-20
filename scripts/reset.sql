-- 테스트마다 실행: psql -h <rds-endpoint> -U coupon -d coupon -f reset.sql
-- 재고 수량은 :qty 로 지정 (기본 100):  psql ... -v qty=100 -f reset.sql
\if :{?qty}
\else
\set qty 100
\endif
BEGIN;
TRUNCATE coupon_issues RESTART IDENTITY;
DELETE FROM events;
INSERT INTO events (id, name, total_qty, remaining_qty) VALUES (1, 'First-come coupon', :qty, :qty);
COMMIT;

-- 검증용
SELECT remaining_qty FROM events WHERE id = 1;
SELECT count(*) AS issued, count(DISTINCT user_id) AS distinct_users FROM coupon_issues;
