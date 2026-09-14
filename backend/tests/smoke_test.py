# -*- coding: utf-8 -*-
"""End-to-end smoke test: login as each role and hit key endpoints."""
import os
import sys

BACKEND = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, BACKEND)

from dotenv import load_dotenv

load_dotenv(os.path.join(BACKEND, ".env"))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def login(email, password="Demo@123"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        return None, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, None


accounts = [
    ("admin@platform.local", "PLATFORM_ADMIN"),
    ("admin@stmarys.demo", "HOSPITAL_ADMIN"),
    ("campaign@stmarys.demo", "CAMPAIGN_MANAGER"),
    ("clinical@stmarys.demo", "CLINICAL_REVIEWER"),
]

for email, role in accounts:
    headers, err = login(email)
    print(f"\n=== {email} ({role}) ===")
    if err:
        print("  LOGIN FAILED:", err)
        continue
    me = client.get("/api/v1/auth/me", headers=headers)
    print("  /auth/me:", me.status_code, me.json().get("role") if me.status_code == 200 else me.text[:120])
    d = client.get("/api/v1/dashboard/campaign-manager", headers=headers)
    print("  /dashboard/campaign-manager:", d.status_code, str(d.json())[:180] if d.status_code == 200 else d.text[:120])
    q = client.get("/api/v1/queue/status", headers=headers)
    print("  /queue/status:", q.status_code, str(q.json())[:160] if q.status_code == 200 else q.text[:120])
    c = client.get("/api/v1/campaigns", headers=headers)
    print("  /campaigns:", c.status_code, len(c.json()) if c.status_code == 200 else c.text[:120])
    p = client.get("/api/v1/patients", headers=headers)
    print("  /patients:", p.status_code, len(p.json()) if p.status_code == 200 else p.text[:120])

# Negative tests
print("\n=== NEGATIVE TESTS ===")
print("  no token:", client.get("/api/v1/patients").status_code)
print("  bad token:", client.get("/api/v1/patients", headers={"Authorization": "Bearer nope"}).status_code)
r = client.post("/api/v1/auth/login", json={"email": "admin@stmarys.demo", "password": "wrong"})
print("  bad password:", r.status_code)