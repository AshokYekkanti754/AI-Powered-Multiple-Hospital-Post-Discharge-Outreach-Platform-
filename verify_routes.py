"""Route-level smoke test: boots the real FastAPI app and exercises every
endpoint the frontend calls. Exit code 0 = all green."""
import sys, json
sys.path.insert(0, "backend")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
fails = []


def hit(name, method, url, token=None, expect=200, **kw):
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = getattr(client, method)(url, headers=headers, **kw)
    ok = r.status_code == expect if isinstance(expect, int) else r.status_code in expect
    if not ok:
        fails.append((name, method, url, r.status_code, r.text[:200]))
    print(f"[{'OK ' if ok else 'FAIL'}] {name:38s} {method.upper():6s} {url:52s} -> {r.status_code}")
    return r


# ---------- login ----------
r = client.post("/api/v1/auth/login", json={"email": "admin@stmarys.demo", "password": "Demo@123"})
print("[OK ] login hospital admin" if r.status_code == 200 else f"[FAIL] login hospital admin -> {r.status_code}: {r.text[:200]}")
tok_h = r.json()["access_token"] if r.status_code == 200 else None

r = client.post("/api/v1/auth/login", json={"email": "admin@platform.local", "password": "Demo@123"})
print("[OK ] login platform admin" if r.status_code == 200 else f"[FAIL] login platform admin -> {r.status_code}: {r.text[:200]}")
tok_p = r.json()["access_token"] if r.status_code == 200 else None

# ---------- bad login must be 401, never a 500 ----------
hit("bad login (expect 401)", "post", "/api/v1/auth/login", json={"email": "nobody@x.io", "password": "wrong"}, expect=401)
# malformed content-type must be 422 (this used to 500 via the handler crash)
hit("malformed login (expect 422)", "post", "/api/v1/auth/login", data={"email": "a", "password": "b"}, expect=422)

# ---------- public / health ----------
hit("health", "get", "/api/v1/health")
hit("queue status", "get", "/api/v1/queue/status", tok_h)
hit("notifications", "get", "/api/v1/notifications", tok_h)

# ---------- dashboard ----------
d = hit("dashboard campaign-manager", "get", "/api/v1/dashboard/campaign-manager", tok_h)
if d.status_code == 200:
    j = d.json()
    print("       dashboard keys:", sorted(j.keys())[:14])

# ---------- queue ----------
hit("queue status again", "get", "/api/v1/queue/status", tok_h)

# ---------- calls: the pipeline driver ----------
n = hit("demo batch (5)", "post", "/api/v1/calls/demo-batch?count=5", tok_h)
if n.status_code == 200:
    print("       demo-batch ->", json.dumps(n.json())[:200])
hit("call history", "get", "/api/v1/calls/history?limit=10", tok_h)
hit("manual followups", "get", "/api/v1/calls/manual-followups", tok_h)

# ---------- escalations ----------
e = hit("escalations list", "get", "/api/v1/escalations", tok_h)
esc_id = None
if e.status_code == 200:
    items = e.json() if isinstance(e.json(), list) else e.json().get("items", [])
    if items:
        esc_id = items[0].get("id")
if esc_id:
    hit("escalation acknowledge", "post", f"/api/v1/escalations/{esc_id}/acknowledge", tok_h)
    hit("escalation resolve", "post", f"/api/v1/escalations/{esc_id}/resolve", tok_h, json={"notes": "reviewed"})
else:
    print("[i]   no escalations to ack/resolve")

# ---------- patients ----------
p = hit("patients list", "get", "/api/v1/patients", tok_h)
pat_id = None
if p.status_code == 200:
    items = p.json() if isinstance(p.json(), list) else p.json().get("items", [])
    if items:
        pat_id = items[0].get("id")
if pat_id:
    hit("patient timeline", "get", f"/api/v1/patients/{pat_id}/timeline", tok_h)
    hit("patient eligibility", "post", f"/api/v1/patients/eligibility-check?patient_id={pat_id}", tok_h, json={})

# ---------- campaigns ----------
c = hit("campaigns list", "get", "/api/v1/campaigns", tok_h)
camp_id = None
if c.status_code == 200:
    rows = c.json() if isinstance(c.json(), list) else c.json().get("items", [])
    if rows:
        camp_id = rows[0].get("id")
if camp_id:
    hit("campaign pause", "post", f"/api/v1/campaigns/{camp_id}/pause", tok_h, expect=[200, 409])
    hit("campaign start", "post", f"/api/v1/campaigns/{camp_id}/start", tok_h)

# ---------- AI (open-source provider status) ----------
hit("ai metrics", "get", "/api/v1/ai/metrics", tok_h)
pr = hit("ai provider status", "get", "/api/v1/ai/provider-status", tok_h)
if pr.status_code == 200:
    print("       provider:", json.dumps(pr.json()))
hit("ai protocols", "get", "/api/v1/ai/protocols", tok_h)
hit("ai logs", "get", "/api/v1/ai/logs?limit=10", tok_h)
hit("ai triage evaluate", "post", "/api/v1/ai/triage/evaluate", tok_h, json={"transcript": "I have mild swelling but no pain."})

# ---------- safety / hospitals / auth-me ----------
hit("safety reports", "get", "/api/v1/safety/reports", tok_h)
hit("hospital me", "get", "/api/v1/hospitals/me", tok_h)
hit("auth me", "get", "/api/v1/auth/me", tok_h)
hit("users list", "get", "/api/v1/users", tok_h)

# ---------- auth guard ----------
hit("unauthenticated dashboard (expect 401)", "get", "/api/v1/dashboard/campaign-manager", expect=401)

print()
if fails:
    print(f"=== {len(fails)} FAILURES ===")
    for f in fails:
        print("FAIL:", f)
    sys.exit(1)
print("=== ALL ROUTES GREEN ===")
