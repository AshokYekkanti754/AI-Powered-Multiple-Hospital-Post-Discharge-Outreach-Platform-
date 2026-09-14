import uuid  # noqa: F401  (kept for future ID parsing helpers)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.v1.deps import db_session, get_current_context
from app.core.redis import semaphore
from app.db.models.call import Call
from app.db.models.campaign import Campaign
from app.db.models.escalation import Escalation
from app.db.models.hospital import Hospital
from app.db.models.manual_followup import ManualFollowUp
from app.db.models.patient import Patient
from app.db.models.queue_task import QueueTask, QueueTaskStatus
from app.middleware.tenant import TenantContext
from app.services.ai_observability import metrics
from app.services.queue_engine import queue_counts

router = APIRouter()


def _resolve_hospital(db: Session, context: TenantContext, hospital_id: str | None = None):
    """Hospital-scoped callers use their own tenant; platform admins may pass ?hospital_id=."""
    if context.hospital_id is not None:
        hospital = db.query(Hospital).filter(Hospital.id == context.hospital_id).one_or_none()
        if hospital is None:
            raise HTTPException(status_code=404, detail="Hospital not found")
        return hospital
    if hospital_id:
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).one_or_none()
        if hospital is None:
            raise HTTPException(status_code=404, detail="Hospital not found")
        return hospital
    hospital = db.query(Hospital).order_by(Hospital.created_at.asc()).first()
    if hospital is None:
        raise HTTPException(status_code=404, detail="No hospitals onboarded yet")
    return hospital


def _summary(db: Session, hospital_id) -> dict:
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).one_or_none()
    if hospital is None:
        return {
            "active_calls": 0, "max_capacity": 0, "pending_tasks": {},
            "completion_rate": 0.0, "patients": 0, "campaigns": 0,
            "open_escalations": 0, "ai_metrics": {"requests": 0, "cost": 0.0},
        }
    active = semaphore.active_count(str(hospital.id))
    counts = queue_counts(db, hospital.id)
    completed = counts.get("COMPLETED", 0)
    total = sum(counts.values())
    calls = db.query(Call).filter(Call.hospital_id == hospital.id).count()
    return {
        "hospital_id": str(hospital.id),
        "hospital_name": hospital.name,
        "active_calls": active,
        "max_capacity": hospital.max_concurrent_calls,
        "pending_tasks": counts,
        "completion_rate": completed / total if total else 0.0,
        "patients": db.query(Patient).filter(Patient.hospital_id == hospital.id).count(),
        "campaigns": db.query(Campaign).filter(Campaign.hospital_id == hospital.id).count(),
        "total_calls": calls,
        "open_escalations": db.query(Escalation).filter(Escalation.hospital_id == hospital.id, Escalation.status == "OPEN").count(),
        "manual_followups": db.query(ManualFollowUp).filter(ManualFollowUp.hospital_id == hospital.id).count(),
        "ai_metrics": metrics(db, hospital_id=hospital.id),
        "recent_calls": [{"id": str(r.id), "outcome": r.outcome.value, "at": r.created_at}
                         for r in db.query(Call).filter(Call.hospital_id == hospital.id).order_by(Call.created_at.desc()).limit(8).all()],
        "top_queue": [{"id": str(t.id), "status": t.status.value, "priority": t.priority_score}
                      for t in db.query(QueueTask).filter(QueueTask.hospital_id == hospital.id).order_by(QueueTask.priority_score.desc()).limit(8).all()],
    }


@router.get("/campaign-manager")
def campaign_manager(hospital_id: str | None = None, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    hospital = _resolve_hospital(db, context, hospital_id)
    return _summary(db, hospital.id)


@router.get("/platform")
def platform_dashboard(db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    if context.role != "PLATFORM_ADMIN":
        raise HTTPException(status_code=403, detail="Platform admins only")
    hospitals = db.query(Hospital).all()
    return {
        "hospitals": [
            {"id": str(h.id), "name": h.name, "summary": _summary(db, h.id)} for h in hospitals
        ],
        "total_patients": db.query(Patient).count(),
        "total_campaigns": db.query(Campaign).count(),
    }


@router.get("/admin")
def admin_dashboard(hospital_id: str | None = None, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    hospital = _resolve_hospital(db, context, hospital_id)
    return _summary(db, hospital.id)

