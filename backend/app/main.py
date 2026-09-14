from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import ai, auth, campaigns, calls, dashboard, ehr, escalations, health as health_endpoint, hospitals, notifications, patients, queue, safety, users, ws_queue
from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.middleware.tenant import TenantContextMiddleware

app = FastAPI(title="Multi-Hospital Post-Discharge Outreach Platform", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:3001",
        "http://localhost:3001",
        "http://127.0.0.1:3002",
        "http://localhost:3002",
        "http://127.0.0.1:3003",
        "http://localhost:3003",
        "http://127.0.0.1:3004",
        "http://localhost:3004",
        "https://ai-powered-multiple-hospital-post-d-rho.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantContextMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    # Pydantic v2 error payloads can contain raw bytes (e.g. invalid form
    # uploads); jsonable_encoder makes every value JSON-safe so this handler
    # can never itself crash and turn a 422 into a 500.
    safe = jsonable_encoder(
        exc.errors(),
        custom_encoder={bytes: lambda b: b.decode("utf-8", errors="replace")},
    )
    return JSONResponse(status_code=422, content={"detail": safe})


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(hospitals.router, prefix="/api/v1/hospitals", tags=["hospitals"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["campaigns"])
app.include_router(queue.router, prefix="/api/v1/queue", tags=["queue"])
app.include_router(patients.router, prefix="/api/v1/patients", tags=["patients"])
app.include_router(ehr.router, prefix="/api/v1/ehr", tags=["ehr"])
app.include_router(calls.router, prefix="/api/v1/calls", tags=["calls"])
app.include_router(escalations.router, prefix="/api/v1/escalations", tags=["escalations"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["ai"])
app.include_router(safety.router, prefix="/api/v1/safety", tags=["safety"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(ws_queue.router, prefix="/api/v1", tags=["stream"])
app.include_router(health_endpoint.router, prefix="/api/v1/health", tags=["health"])


@app.on_event("startup")
def on_startup():
    # Milestone 1.1 uses create_all for simplicity; a real Alembic migration
    # chain should replace this before production use.
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:  # never crash boot on DB issues; endpoints 500 with detail
        print(f"[startup] WARNING: create_all failed: {exc}")
        return
    # Lightweight column back-fill for REQ-2 (`escalations.timeout_triggered`)
    # on databases created before the column existed.
    _ensure_escalation_timeout_column()
    if settings.ENVIRONMENT == "development":
        # Database maintenance: ensure the demo tenants/users exist so the
        # platform is usable out-of-the-box in local development.
        from app.db.seed import seed_demo_data

        db = SessionLocal()
        try:
            result = seed_demo_data(db)
            if result.get("seeded"):
                print("[startup] Seeded demo data — admin@platform.local / Demo@123")
        except Exception as exc:
            print(f"[startup] WARNING: seed failed: {exc}")
        finally:
            db.close()


def _ensure_escalation_timeout_column() -> None:
    """ALTER the escalations table to add ``timeout_triggered`` if missing.

    create_all never migrates existing tables, so we add the REQ-2 column
    explicitly. The DDL is dialect-aware (Postgres needs a boolean literal).
    """
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(engine)
        if "escalations" not in inspector.get_table_names():
            return
        columns = {c["name"] for c in inspector.get_columns("escalations")}
        if "timeout_triggered" in columns:
            return
        if engine.dialect.name == "postgresql":
            ddl = "ALTER TABLE escalations ADD COLUMN timeout_triggered BOOLEAN NOT NULL DEFAULT FALSE"
        else:  # sqlite and others accept integer 0 as a boolean default
            ddl = "ALTER TABLE escalations ADD COLUMN timeout_triggered BOOLEAN NOT NULL DEFAULT 0"
        with engine.begin() as conn:
            conn.execute(text(ddl))
        print("[startup] Added column escalations.timeout_triggered")
    except Exception as exc:  # never crash boot on migration failure
        print(f"[startup] WARNING: escalation timeout column migration failed: {exc}")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    import traceback
    traceback.print_exc()
    status = getattr(exc, "status_code", 500)
    detail = str(exc) if settings.ENVIRONMENT == "development" else "Internal server error"
    return JSONResponse(status_code=status if isinstance(status, int) else 500, content={"detail": detail})
