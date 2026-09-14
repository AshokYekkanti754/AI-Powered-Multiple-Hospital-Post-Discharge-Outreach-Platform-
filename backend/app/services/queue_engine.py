"""Tenant-scoped queue creation, claiming, and status operations."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.queue_events import publish_queue_event
from app.core.redis import semaphore
from app.db.models.campaign import Campaign, CampaignStatus
from app.db.models.queue_task import QueueTask, QueueTaskStatus


def claim_next_task(db: Session, *, hospital_id: uuid.UUID, worker_id: str, capacity: int, now: datetime | None = None) -> QueueTask | None:
    now = now or datetime.now(timezone.utc)
    with semaphore.acquire(str(hospital_id), capacity) as acquired:
        if not acquired:
            return None
        task = (db.query(QueueTask)
            .join(Campaign, Campaign.id == QueueTask.campaign_id)
            .filter(QueueTask.hospital_id == hospital_id,
                    QueueTask.status.in_([QueueTaskStatus.PENDING, QueueTaskStatus.SCHEDULED, QueueTaskStatus.RETRY_SCHEDULED]),
                    Campaign.hospital_id == hospital_id,
                    Campaign.status == CampaignStatus.RUNNING,
                    (QueueTask.scheduled_for.is_(None) | (QueueTask.scheduled_for <= now)))
            .order_by(QueueTask.priority_score.desc(), QueueTask.scheduled_for.asc(), QueueTask.id.asc())
            .with_for_update(skip_locked=True).first())
        if task is None:
            return None
        task.status = QueueTaskStatus.CALLING
        task.call_started_at = now
        task.locked_by_worker = worker_id
        db.commit()
        db.refresh(task)
        try:
            # REQ-1: PENDING -> CALLING transition -> live telemetry publish.
            publish_queue_event(db, hospital_id=hospital_id)
        except Exception:  # noqa: BLE001
            pass
        return task


def queue_counts(db: Session, hospital_id: uuid.UUID) -> dict[str, int]:
    rows = db.query(QueueTask.status, func.count(QueueTask.id)).filter(QueueTask.hospital_id == hospital_id).group_by(QueueTask.status).all()
    return {status.value: count for status, count in rows}
