"""Celery wrapper for the 15-minute escalation backup check (REQ-2).

When an ``ESCALATION_CREATED`` event fires, ``escalation_service`` dispatches
``check_escalation_timeout.apply_async(args=[escalation_id], countdown=900)``.
This task wakes up 15 minutes later and elevates any escalation that is still
OPEN to URGENT, writes a secondary Hospital-Admin notification and marks
``timeout_triggered = True``.

``_check_escalation_timeout_impl`` is the testable core; the Celery task
(deferred by bind) is a thin wrapper over it.
"""
from __future__ import annotations

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.escalation_service import enforce_escalation_timeout


def _check_escalation_timeout_impl(escalation_id: str, db=None) -> dict:
    """Execute the 15-minute escalation timeout check.

    ``db`` is injected by tests; production uses ``SessionLocal``.
    """
    session = db if db is not None else SessionLocal()
    try:
        elevated = enforce_escalation_timeout(session, escalation_id=escalation_id, timeout_minutes=15)
        return {"escalation_id": str(escalation_id), "elevated": elevated}
    finally:
        if db is None:
            session.close()


try:
    from celery import Celery

    celery_app = Celery("escalation_timeout", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

    @celery_app.task(name="escalation.check_timeout")
    def check_escalation_timeout(escalation_id: str) -> dict:
        return _check_escalation_timeout_impl(escalation_id)
except ImportError:
    celery_app = None
    check_escalation_timeout = _check_escalation_timeout_impl
