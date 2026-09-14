import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.v1.deps import db_session, get_current_context, require_roles
from app.db.models.campaign import Campaign, CampaignStatus
from app.db.models.encounter import Encounter
from app.db.models.patient import Patient
from app.db.models.queue_task import QueueTask, QueueTaskStatus
from app.db.models.user import UserRole
from app.middleware.tenant import TenantContext
from app.services.eligibility_engine import evaluate_eligibility
from app.services.priority_calculator import calculate_priority_score

router = APIRouter()


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    follow_up_window_hours: int = Field(default=48, gt=0)
    max_retries: int = Field(default=3, ge=0)
    campaign_priority: int = Field(default=3, ge=1, le=5)


class CampaignOut(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    name: str
    status: CampaignStatus
    follow_up_window_hours: int
    max_retries: int
    campaign_priority: int

    class Config:
        from_attributes = True


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    return db.query(Campaign).filter(Campaign.hospital_id == context.hospital_id).order_by(Campaign.created_at.desc()).all()


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(payload: CampaignCreate, db: Session = Depends(db_session), context: TenantContext = Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.CAMPAIGN_MANAGER))):
    campaign = Campaign(hospital_id=context.hospital_id, **payload.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def _campaign_or_404(db: Session, campaign_id: uuid.UUID, hospital_id: str) -> Campaign:
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.hospital_id == hospital_id).first()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/{campaign_id}/start", response_model=CampaignOut)
def start_campaign(campaign_id: uuid.UUID, db: Session = Depends(db_session), context: TenantContext = Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.CAMPAIGN_MANAGER))):
    campaign = _campaign_or_404(db, campaign_id, context.hospital_id)
    if campaign.status not in {CampaignStatus.DRAFT, CampaignStatus.READY, CampaignStatus.PAUSED}:
        raise HTTPException(status_code=409, detail=f"Campaign cannot start from {campaign.status.value}")
    now = datetime.now(timezone.utc)
    encounters = db.query(Encounter).join(Patient, Patient.id == Encounter.patient_id).filter(Encounter.hospital_id == context.hospital_id, Patient.consent_status.is_(True)).all()
    existing = {row.patient_id for row in db.query(QueueTask).filter(QueueTask.campaign_id == campaign.id).all()}
    for encounter in encounters:
        result = evaluate_eligibility(encounter_id=str(encounter.id), patient_id=str(encounter.patient_id), discharge_timestamp=encounter.discharge_timestamp, follow_up_window_hours=campaign.follow_up_window_hours, risk_score=encounter.risk_score, consent_status=True, now=now)
        if not result.eligible or encounter.patient_id in existing:
            continue
        db.add(QueueTask(hospital_id=context.hospital_id, campaign_id=campaign.id, patient_id=encounter.patient_id, status=QueueTaskStatus.PENDING, priority_score=calculate_priority_score(risk_score=encounter.risk_score, time_remaining_hours=result.hours_remaining_in_window, total_followup_window_hours=campaign.follow_up_window_hours, campaign_priority=campaign.campaign_priority)))
    campaign.status = CampaignStatus.RUNNING
    db.commit()
    db.refresh(campaign)
    return campaign


@router.post("/{campaign_id}/pause", response_model=CampaignOut)
def pause_campaign(campaign_id: uuid.UUID, db: Session = Depends(db_session), context: TenantContext = Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.CAMPAIGN_MANAGER))):
    campaign = _campaign_or_404(db, campaign_id, context.hospital_id)
    if campaign.status != CampaignStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Only running campaigns can be paused")
    campaign.status = CampaignStatus.PAUSED
    db.commit()
    db.refresh(campaign)
    return campaign
