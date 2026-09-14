"""Celery task entry point; call integrations remain deferred."""
from __future__ import annotations

import os
from app.core.config import settings

try:
    from celery import Celery
except ImportError:
    Celery = None

celery_app = Celery("outreach_queue", broker=settings.REDIS_URL, backend=settings.REDIS_URL) if Celery else None
if celery_app:
    celery_app.conf.update(task_acks_late=True, worker_prefetch_multiplier=1)


def _process(task_id: str, hospital_id: str) -> dict:
    return {"task_id": task_id, "hospital_id": hospital_id, "worker_id": str(os.getpid())}


if celery_app:
    process_queue_task = celery_app.task(name="queue.process_task")(_process)
else:
    process_queue_task = _process
