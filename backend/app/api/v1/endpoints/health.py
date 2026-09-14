"""System component health checks (REQ-7).

``GET /api/v1/health`` reports the status of every subsystem the platform
depends on using the ``HEALTHY`` / ``DEGRADED`` / ``UNAVAILABLE`` vocabulary,
plus an overall roll-up.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.queue_events import redis_available
from app.db.models.observation import Observation
from app.db.session import get_db

router = APIRouter()

HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
UNAVAILABLE = "UNAVAILABLE"


def _component(name: str, status: str, detail: str = "") -> dict:
    return {"component": name, "status": status, "detail": detail}


@router.get("")
def api_health(db: Session = Depends(get_db)):
    components: list[dict] = []

    # 1. Backend API — self check, always healthy when reachable.
    components.append(_component("backend_api", HEALTHY, "FastAPI responding"))

    # 2. Database.
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        db_status, db_detail = UNAVAILABLE, f"database unreachable: {exc}"
    else:
        db_status, db_detail = HEALTHY, "SELECT 1 ok"
    components.append(_component("database", db_status, db_detail))

    # 3. Queue workers & Redis.
    if redis_available():
        queue_status, queue_detail = HEALTHY, "Redis broker reachable"
    elif settings.REDIS_URL.startswith("redis"):
        queue_status, queue_detail = DEGRADED, "Redis unreachable — in-memory queue fallback active"
    else:
        queue_status, queue_detail = DEGRADED, "Redis not configured — in-memory queue fallback active"
    components.append(_component("queue_workers_redis", queue_status, queue_detail))

    # 4. AI Providers (Groq / OpenRouter / Google fallback chain).
    provider_key = settings.AI_PROVIDER
    real_keys = any(
        key and not key.startswith(("your_", "sk-dummy-", "dummy-", "change-me"))
        for key in (settings.GROQ_API_KEY, settings.OPENROUTER_API_KEY, settings.GOOGLE_API_KEY)
    )
    if provider_key == "mock":
        ai_status, ai_detail = HEALTHY, "Deterministic mock LLM (offline-safe)"
    elif real_keys:
        ai_status, ai_detail = HEALTHY, f"Provider '{provider_key}' configured"
    else:
        ai_status, ai_detail = DEGRADED, f"Provider '{provider_key}' has placeholder keys — mock fallback active"
    components.append(_component("ai_providers", ai_status, ai_detail))

    # 5. Mock EHR Service.
    try:
        db.query(Observation).limit(1).all()
        ehr_status, ehr_detail = HEALTHY, "Mock EHR tables reachable"
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        ehr_status, ehr_detail = UNAVAILABLE, f"mock EHR error: {exc}"
    components.append(_component("mock_ehr", ehr_status, ehr_detail))

    # 6. WebSocket Telemetry Engine.
    if redis_available():
        ws_status, ws_detail = HEALTHY, "Publishing to queue_events:{hospital_id} via Redis pub/sub"
    else:
        ws_status, ws_detail = DEGRADED, "In-process snapshot stream active (Redis absent)"
    components.append(_component("websocket_telemetry", ws_status, ws_detail))

    statuses = {c["status"] for c in components}
    if not db_ok or UNAVAILABLE in statuses:
        overall = "unavailable"
    elif DEGRADED in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.ENVIRONMENT,
        "components": components,
    }