import uuid  # noqa: F401
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.v1.deps import db_session, get_current_context
from app.core.redis import semaphore
from app.db.models.hospital import Hospital
from app.middleware.tenant import TenantContext
from app.services.queue_engine import queue_counts

router = APIRouter()


def _hospital_or_404(db: Session, context: TenantContext, hospital_id: str | None = None) -> Hospital:
    if context.hospital_id is not None:
        hospital = db.query(Hospital).filter(Hospital.id == context.hospital_id).first()
    elif hospital_id:
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    else:
        hospital = db.query(Hospital).order_by(Hospital.created_at.asc()).first()
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return hospital


@router.get("/status")
def queue_status(hospital_id: str | None = None, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    hospital = _hospital_or_404(db, context, hospital_id)
    active = semaphore.active_count(str(hospital.id))
    capacity = hospital.max_concurrent_calls
    return {"hospital_id": str(hospital.id), "hospital_name": hospital.name,
            "active_calls": active, "max_capacity": capacity,
            "utilization": active / capacity if capacity else 0.0,
            "pending_tasks": queue_counts(db, hospital.id)}

