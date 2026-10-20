// 같은 ALB 주소의 /api/* 로 호출하므로 Backend 주소 노출/CORS 설정이 필요 없다.
const EVENT_ID = 1;
const $ = (id) => document.getElementById(id);

async function loadRemaining() {
  try {
    const r = await fetch(`/api/events/${EVENT_ID}`);
    if (!r.ok) throw new Error(r.status);
    const d = await r.json();
    $("remaining").textContent = d.remaining;
    $("source").textContent = d.source;
  } catch {
    $("remaining").textContent = "?";
    $("source").textContent = "조회 실패";
  }
}

function show(text, kind) {
  const el = $("message");
  el.textContent = text;
  el.className = kind;
}

async function loadCoupons() {
  const userId = $("userId").value.trim();
  if (!userId) return show("사용자 ID를 입력하세요.", "error");
  const r = await fetch(`/api/users/${encodeURIComponent(userId)}/coupons`);
  if (!r.ok) return show("내역 조회에 실패했습니다.", "error");
  const d = await r.json();
  const ul = $("coupons");
  ul.replaceChildren();
  if (d.coupons.length === 0) {
    const li = document.createElement("li");
    li.textContent = "발급 내역 없음";
    ul.append(li);
  }
  for (const c of d.coupons) {
    const li = document.createElement("li");
    li.textContent = `#${c.couponId} · 이벤트 ${c.eventId} · ${new Date(c.issuedAt).toLocaleString()}`;
    ul.append(li);
  }
}

$("issue-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("issue-btn");
  btn.disabled = true;
  try {
    const r = await fetch(`/api/events/${EVENT_ID}/issue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userId: $("userId").value.trim() }),
    });
    if (r.status === 201) show("쿠폰이 발급되었습니다!", "ok");
    else if (r.status === 409) show("이미 발급받은 사용자입니다.", "warn");
    else if (r.status === 410) show("쿠폰이 모두 소진되었습니다.", "warn");
    else if (r.status === 422) show("사용자 ID 형식이 올바르지 않습니다.", "error");
    else show(`오류가 발생했습니다 (HTTP ${r.status}).`, "error");
    await loadRemaining();
    if (r.status === 201 || r.status === 409) await loadCoupons();
  } catch {
    show("네트워크 오류가 발생했습니다.", "error");
  } finally {
    btn.disabled = false;
  }
});

$("refresh-coupons").addEventListener("click", loadCoupons);

loadRemaining();
setInterval(loadRemaining, 5000);
