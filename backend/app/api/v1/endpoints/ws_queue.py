import asyncio
import threading

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.queue_events import (
    _latest,
    _lock,
    redis_available,
    snapshot_revision,
    subscribe_channels,
)
from app.db.session import SessionLocal
from app.db.models.hospital import Hospital

router = APIRouter()


@router.websocket("/ws/queue-stream")
async def queue_stream(websocket: WebSocket, hospital_id: str | None = None):
    """Stream live queue stats for one hospital (or all hospitals).

    When Redis is reachable the payloads are delivered as they are published on
    ``queue_events:{hospital_id}``; otherwise the in-process snapshot revision
    is polled (sub-second) so dashboards still update without a page refresh.
    """
    await websocket.accept()
    db: Session = SessionLocal()
    try:
        if hospital_id:
            hospital = db.query(Hospital).filter(Hospital.id == hospital_id).one_or_none()
            hospital_ids = [str(hospital.id)] if hospital else []
        else:
            hospital_ids = [str(h.id) for h in db.query(Hospital).all()]
    finally:
        db.close()

    stop = threading.Event()
    redis_queue: asyncio.Queue | None = None
    redis_ok = redis_available() and bool(hospital_ids)
    if redis_ok:
        redis_queue = asyncio.Queue()

        def _on_message(payload: dict):
            if redis_queue is not None:
                try:
                    redis_queue.put_nowait(payload)
                except Exception:  # noqa: BLE001
                    pass

        listener = threading.Thread(
            target=subscribe_channels,
            args=(hospital_ids, _on_message, stop),
            daemon=True,
        )
        listener.start()

    last_versions = {hid: -1 for hid in hospital_ids}
    try:
        while True:
            # 1) Drain any Redis-published payloads as fast as they arrive.
            if redis_queue is not None:
                while not redis_queue.empty():
                    try:
                        payload = redis_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    await websocket.send_json(payload)
            # 2) Always stream the freshest in-process snapshot for each hospital.
            pushed = False
            for hid in hospital_ids:
                version = snapshot_revision(hid)
                if version != last_versions.get(hid, -1):
                    last_versions[hid] = version
                    with _lock:
                        payload = _latest.get(hid)
                    if payload is not None:
                        await websocket.send_json(payload)
                        pushed = True
            # 3) Initial/heartbeat snapshot when nothing changed inside the window.
            if not pushed:
                if last_versions.get("__first__") is None:
                    last_versions["__first__"] = True
                    snapshot = _snapshot_payload(hospital_ids)
                    await websocket.send_json({"event": "queue_snapshot", "hospitals": snapshot})
            await asyncio.sleep(0.5)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        stop.set()


def _snapshot_payload(hospital_ids):
    """Build {hospital_id, active_calls, max_capacity, pending, completed, escalated, retrying} per hospital."""
    db: Session = SessionLocal()
    try:
        hospitals = db.query(Hospital).filter(Hospital.id.in_(hospital_ids)).all() if hospital_ids else db.query(Hospital).all()
        payload = []
        for h in hospitals:
            from app.core.queue_events import stats_payload

            payload.append(stats_payload(db, h))
        return payload
    finally:
        db.close()

