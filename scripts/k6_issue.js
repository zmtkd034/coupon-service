// T3 Sold-out: 재고 100 + 서로 다른 userId 500회  ->  201 100 / 410 400
// T2 Duplicate: SCENARIO=dup  ->  동일 userId 100회 -> 201 1 / 409 99
// 실행: k6 run -e BASE=http://<alb-dns> scripts/k6_issue.js
import http from "k6/http";
import { Counter } from "k6/metrics";

const BASE = __ENV.BASE || "http://localhost:8000";
const dup = __ENV.SCENARIO === "dup";
const N = dup ? 100 : 500;

const c201 = new Counter("issue_201");
const c409 = new Counter("issue_409");
const c410 = new Counter("issue_410");
const cOther = new Counter("issue_other");

export const options = {
  scenarios: {
    burst: { executor: "shared-iterations", vus: 100, iterations: N, maxDuration: "60s" },
  },
};

export default function () {
  const userId = dup ? "dup-user" : `user-${__VU}-${__ITER}-${Date.now()}`;
  const r = http.post(`${BASE}/api/events/1/issue`, JSON.stringify({ userId }),
    { headers: { "Content-Type": "application/json" } });
  if (r.status === 201) c201.add(1);
  else if (r.status === 409) c409.add(1);
  else if (r.status === 410) c410.add(1);
  else cOther.add(1);
}
