// T4 Cache: 재고 조회 반복. CACHE_ENABLED=true/false 로 Backend 를 각각 띄워 비교한다.
// 실행 전후 GET /api/stats 로 cache_hit / cache_miss / db_read 를 기록한다.
import http from "k6/http";

const BASE = __ENV.BASE || "http://localhost:8000";

export const options = { vus: 50, duration: "30s" };

export default function () {
  http.get(`${BASE}/api/events/1`);
}
