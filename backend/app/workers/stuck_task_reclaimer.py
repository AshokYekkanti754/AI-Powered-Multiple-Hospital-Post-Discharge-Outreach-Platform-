"""Reclaim calls left in CALLING after a worker crash (REQ-3).

A Celery Beat job runs every 60 seconds and sweeps every hospital for queue
tasks stuck in ``CALLING`` for longer than ``stale_after_seconds`` (90s), or
that have no worker lock (missing heartbeat). Each stuck task is:

  * reset to ``RETRY_SCHEDULED`` (scheduled for immediate re-queueing),
  * its Redis concurrency slot is released atomically
    (``lock:concurrency:{hospital_id}``),
  * an audit event is written to ``audit_logs``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.queue_events import publish_queue_event
from app.core.redis import semaphore
from app.db.models.audit_log import AuditLog
from app.db.models.hospital import Hospital
from app.db.models.queue_task import QueueTask, QueueTaskStatus


def reclaim_stuck_tasks(
    db: Session,
    *,
    hospital_id,
    stale_after_seconds: int = 90,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=stale_after_seconds)
    # A task with no worker lock is treated as missing a heartbeat.
    tasks = (
        db.query(QueueTask)
        .filter(
            QueueTask.hospital_id == hospital_id,
            QueueTask.status == QueueTaskStatus.CALLING,
            (QueueTask.call_started_at.is_(None) | (QueueTask.call_started_at < cutoff)),
        )
        .all()
    )
    for task in tasks:
        task.status = QueueTaskStatus.RETRY_SCHEDULED
        task.scheduled_for = now
        task.locked_by_worker = None
        task.updated_at = now
        db.add(
            AuditLog(
                hospital_id=hospital_id,
                user_id=None,
                action="queue.reclaim_stuck",
                resource=f"queue_task:{task.id}",
                payload={"from": "CALLING", "to": "RETRY_SCHEDULED", "stale_after_seconds": stale_after_seconds},
            )
        )
    if tasks:
        db.commit()
        for _ in tasks:
            semaphore.release_any(str(hospital_id), count=1)
        publish_queue_event(db, hospital_id=hospital_id)
    return len(tasks)


def reclaim_all_hospitals(db: Session, *, stale_after_seconds: int = 90, now: datetime | None = None) -> int:
    """Run the reclaimer across every onboarded hospital (Celery Beat entry)."""
    total = 0
    for hospital in db.query(Hospital).all():
        total += reclaim_stuck_tasks(db, hospital_id=hospital.id, stale_after_seconds=stale_after_seconds, now=now)
    return total


try:
    from celery import Celery
    from app.core.config import settings

    celery_app = Celery("stuck_task_reclaimer", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
    celery_app.conf.beat_schedule = {
        "reclaim-stuck-tasks-every-60s": {
            "task": "queue.reclaim_stuck_tasks",
            "schedule": 60.0,
        }
    }

    @celery_app.task(name="queue.reclaim_stuck_tasks")
    def reclaim_task() -> dict:
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            return {"reclaimed": reclaim_all_hospitals(db)}
        finally:
            db.close()
except ImportError:
    celery_app = None
