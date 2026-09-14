import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.v1.deps import db_session, get_current_context
from app.db.models.call import Call, CallOutcome
from app.db.models.queue_task import QueueTask, QueueTaskStatus
from app.events.bus import DomainEvent, bus
from app.middleware.tenant import TenantContext
from app.services.queue_state_machine import apply_call_outcome

router = APIRouter()


class CallOutcomePayload(BaseModel):
    queue_task_id: uuid.UUID
    outcome: CallOutcome
    partial_transcript: str | None = None
    callback_at: datetime | None = None
    duration_seconds: int | None = None


class ProcessNextPayload(BaseModel):
    campaign_id: uuid.UUID | None = None
    patient_seed: int | None = None
    transcript_override: str | None = None
    simulated_outcome: CallOutcome | None = None


@router.post("/process-next")
def process_next(payload: ProcessNextPayload, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    """Run the next PENDING queue task through the full AI call pipeline (synchronous, demo-friendly)."""
    from app.services.call_orchestrator import process_queue_task
    query = db.query(QueueTask).filter(QueueTask.hospital_id == context.hospital_id,
        QueueTask.status.in_([QueueTaskStatus.PENDING, QueueTaskStatus.SCHEDULED, QueueTaskStatus.RETRY_SCHEDULED]))
    if payload.campaign_id is not None:
        query = query.filter(QueueTask.campaign_id == payload.campaign_id)
    task = query.order_by(QueueTask.priority_score.desc()).first()
    if task is None:
        return {"processed": False, "reason": "no_pending_tasks"}
    try:
        result = process_queue_task(db, task_id=task.id, worker_id=f"api:{context.user_id}",
            patient_seed=payload.patient_seed, transcript_override=payload.transcript_override,
            simulated_outcome=payload.simulated_outcome)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"processed": True, **result}


@router.post("/process/{task_id}")
def process_one(task_id: uuid.UUID, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    from app.services.call_orchestrator import process_queue_task
    task = db.query(QueueTask).filter(QueueTask.id == task_id, QueueTask.hospital_id == context.hospital_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Queue task not found")
    try:
        return process_queue_task(db, task_id=task.id, worker_id=f"api:{context.user_id}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/demo-batch")
def demo_batch(count: int = 10, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    """Process up to `count` pending tasks back-to-back so dashboards light up instantly."""
    from app.services.call_orchestrator import process_queue_task
    results = []
    for _ in range(max(1, min(count, 30))):
        task = (db.query(QueueTask).filter(QueueTask.hospital_id == context.hospital_id,
            QueueTask.status.in_([QueueTaskStatus.PENDING, QueueTaskStatus.SCHEDULED, QueueTaskStatus.RETRY_SCHEDULED]))
            .order_by(QueueTask.priority_score.desc()).first())
        if task is None:
            break
        try:
            results.append(process_queue_task(db, task_id=task.id, worker_id=f"api:{context.user_id}"))
        except ValueError as exc:
            results.append({"task_id": str(task.id), "error": str(exc)})
    return {"processed": len(results), "results": results}


@router.get("/history")
def call_history(limit: int = 50, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    rows = db.query(Call).filter(Call.hospital_id == context.hospital_id).order_by(Call.created_at.desc()).limit(limit).all()
    return [{"id": str(r.id), "patient_id": str(r.patient_id), "outcome": r.outcome.value,
             "duration": r.duration_seconds, "transcript": (r.partial_transcript or "")[:600],
             "at": r.created_at} for r in rows]


@router.post("/outcome")
def call_outcome(payload: CallOutcomePayload, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    task = db.query(QueueTask).filter(QueueTask.id == payload.queue_task_id, QueueTask.hospital_id == context.hospital_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Queue task not found")
    try:
        task = apply_call_outcome(db, task=task, outcome=payload.outcome, partial_transcript=payload.partial_transcript, callback_at=payload.callback_at, duration_seconds=payload.duration_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    bus.publish(DomainEvent(event_type="CALL_NO_ANSWER" if payload.outcome in {CallOutcome.NO_ANSWER, CallOutcome.BUSY, CallOutcome.VOICEMAIL} else "CALL_COMPLETED", hospital_id=str(context.hospital_id), payload={"task_id": str(task.id)}))
    return {"task_id": str(task.id), "status": task.status.value, "retry_count": task.retry_count, "scheduled_for": task.scheduled_for}


@router.get("/manual-followups")
def manual_followups(db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    from app.db.models.manual_followup import ManualFollowUp
    rows = db.query(ManualFollowUp).filter(ManualFollowUp.hospital_id == context.hospital_id).order_by(ManualFollowUp.created_at.desc()).all()
    return [{"id": str(row.id), "patient_id": str(row.patient_id), "campaign_id": str(row.campaign_id), "reason": row.reason, "status": row.status.value} for row in rows]

