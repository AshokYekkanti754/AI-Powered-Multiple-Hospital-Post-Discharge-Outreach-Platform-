"""Real-time queue telemetry broker (REQ-1).

Whenever a queue task changes state we publish a compact stats payload to the
Redis channel ``queue_events:{hospital_id}``. WebSocket clients subscribe to
that channel so dashboards update without a page refresh.

When Redis is unreachable (local dev / tests) the broker degrades gracefully:

  * state transitions still update an in-process ``_latest`` snapshot that the
    WebSocket endpoint streams to connected clients (sub-second polling),
  * the Redis ``publish`` call is skipped without raising.

The payload shape is stable so both the Redis subscribers and the in-process
stream deliver the same JSON:

    {
      "event": "queue_update",
      "hospital_id": "...",
      "hospital_name": "...",
      "active_calls": int,
      "max_capacity": int,
      "pending": int,        # PENDING + SCHEDULED
      "completed": int,
      "escalated": int,      # ESCALATED + MANUAL_FOLLOW_UP
      "retrying": int,       # RETRY_SCHEDULED
      "timestamp": "..."
    }
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.redis import semaphore
from app.db.models.hospital import Hospital

_lock = threading.Lock()
_latest: dict[str, dict] = {}
_revision: dict[str, int] = {}

_redis_client = None
_redis_error: str | None = None


def _get_redis():
    """Return the shared Redis client, or None if it is unavailable."""
    global _redis_client, _redis_error
    if _redis_client is None and _redis_error is None:
        try:
            import redis
            from app.core.config import settings

            client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            client.ping()
            _redis_client = client
        except Exception as exc:  # noqa: BLE001 - any redis failure -> offline mode
            _redis_error = str(exc)
    return _redis_client


def redis_available() -> bool:
    """True when the Redis channel backend is reachable."""
    return _get_redis() is not None


def stats_payload(db: Session, hospital: Hospital) -> dict:
    """Build the exact queue-stats payload for one hospital."""
    from app.services.queue_engine import queue_counts  # local import avoids a cycle

    counts = queue_counts(db, hospital.id)
    return {
        "event": "queue_update",
        "hospital_id": str(hospital.id),
        "hospital_name": hospital.name,
        "active_calls": semaphore.active_count(str(hospital.id)),
        "max_capacity": hospital.max_concurrent_calls,
        "pending": int(counts.get("PENDING", 0)) + int(counts.get("SCHEDULED", 0)),
        "completed": int(counts.get("COMPLETED", 0)),
        "escalated": int(counts.get("ESCALATED", 0)) + int(counts.get("MANUAL_FOLLOW_UP", 0)),
        "retrying": int(counts.get("RETRY_SCHEDULED", 0)),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def publish_queue_event(db: Session, *, hospital_id) -> dict | None:
    """Publish the latest queue stats for a hospital to ``queue_events:{id}``.

    Always updates the in-process snapshot (so local WebSockets stream it), and
    publishes to Redis when available. Idempotent and never raises.
    """
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).one_or_none()
    if hospital is None:
        return None
    payload = stats_payload(db, hospital)
    key = str(hospital_id)
    with _lock:
        _latest[key] = payload
        _revision[key] = _revision.get(key, 0) + 1
    client = _get_redis()
    if client is not None:
        try:
            client.publish(f"queue_events:{key}", json.dumps(payload))
        except Exception:  # noqa: BLE001 - telemetry must never break the pipeline
            pass
    return payload


def latest_payload(hospital_id=None):
    """Return the most recent in-process snapshot(s)."""
    with _lock:
        if hospital_id is not None:
            return _latest.get(str(hospital_id))
        return dict(_latest)


def snapshot_revision(hospital_id=None) -> int:
    """Monotonic revision number per hospital; 0 when never published."""
    with _lock:
        if hospital_id is not None:
            return _revision.get(str(hospital_id), 0)
        return sum(_revision.values())


def subscribe_channels(hospital_ids, on_message, stop_event: threading.Event, timeout: float = 1.0):
    """Run a blocking Redis pub/sub loop in a worker thread.

    ``on_message(payload: dict)`` is invoked from this thread for every message
    received on ``queue_events:{hospital_id}`` for the requested hospitals.
    """
    client = _get_redis()
    if client is None:
        return
    pubsub = client.pubsub()
    pubsub.subscribe(*[f"queue_events:{hid}" for hid in hospital_ids])
    try:
        for message in pubsub.listen():
            if stop_event.is_set():
                break
            if message.get("type") != "message":
                continue
            try:
                on_message(json.loads(message["data"]))
            except Exception:  # noqa: BLE001
                pass
    finally:
        try:
            pubsub.close()
        except Exception:  # noqa: BLE001
            pass