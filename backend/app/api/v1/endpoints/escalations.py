import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.v1.deps import db_session, get_current_context, require_roles
from app.db.models.escalation import Escalation, EscalationSeverity, EscalationStatus
from app.db.models.user import UserRole
from app.middleware.tenant import TenantContext
from app.services.escalation_service import acknowledge_escalation, create_escalation, resolve_escalation

router = APIRouter()
REVIEW_ROLES = (UserRole.HOSPITAL_ADMIN, UserRole.CLINICAL_REVIEWER)


def serialize(row: Escalation):
    return {"id": str(row.id), "patient_id": str(row.patient_id), "campaign_id": str(row.campaign_id), "call_id": str(row.call_id) if row.call_id else None, "status": row.status.value, "severity": row.severity.value, "trigger_reason": row.trigger_reason, "assigned_user_id": str(row.assigned_user_id) if row.assigned_user_id else None, "acknowledged_at": row.acknowledged_at, "resolved_at": row.resolved_at}


class CreateEscalationPayload(BaseModel):
    patient_id: uuid.UUID
    campaign_id: uuid.UUID
    call_id: uuid.UUID | None = None
    severity: EscalationSeverity
    trigger_reason: str


class ResolvePayload(BaseModel):
    notes: str = ""


@router.get("")
def list_escalations(status: EscalationStatus | None = Query(None), severity: EscalationSeverity | None = Query(None), db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    query = db.query(Escalation).filter(Escalation.hospital_id == context.hospital_id)
    if status is not None: query = query.filter(Escalation.status == status)
    if severity is not None: query = query.filter(Escalation.severity == severity)
    return [serialize(row) for row in query.order_by(Escalation.created_at.desc()).all()]


@router.post("", status_code=201)
def create(payload: CreateEscalationPayload, db: Session = Depends(db_session), context: TenantContext = Depends(require_roles(*REVIEW_ROLES))):
    return serialize(create_escalation(db, hospital_id=context.hospital_id, **payload.model_dump()))


@router.post("/{escalation_id}/acknowledge")
def acknowledge(escalation_id: uuid.UUID, db: Session = Depends(db_session), context: TenantContext = Depends(require_roles(*REVIEW_ROLES))):
    row = db.query(Escalation).filter(Escalation.id == escalation_id, Escalation.hospital_id == context.hospital_id).first()
    if row is None: raise HTTPException(status_code=404, detail="Escalation not found")
    return serialize(acknowledge_escalation(db, escalation=row, user_id=uuid.UUID(context.user_id)))


@router.post("/{escalation_id}/resolve")
def resolve(escalation_id: uuid.UUID, payload: ResolvePayload, db: Session = Depends(db_session), context: TenantContext = Depends(require_roles(*REVIEW_ROLES))):
    row = db.query(Escalation).filter(Escalation.id == escalation_id, Escalation.hospital_id == context.hospital_id).first()
    if row is None: raise HTTPException(status_code=404, detail="Escalation not found")
    return serialize(resolve_escalation(db, escalation=row, notes=payload.notes))
