import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import time

from app.api.v1.deps import db_session, get_current_context, require_roles
from app.core.security import hash_password
from app.db.models.hospital import Hospital
from app.db.models.user import User, UserRole
from app.middleware.tenant import TenantContext

router = APIRouter()


class OnboardHospitalRequest(BaseModel):
    hospital_name: str
    timezone: str = "UTC"
    max_concurrent_calls: int = 10
    retry_limit: int = 3
    admin_email: str
    admin_full_name: str
    admin_password: str


class HospitalOut(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    max_concurrent_calls: int
    retry_limit: int
    calling_hours_start: time
    calling_hours_end: time

    class Config:
        from_attributes = True


@router.post("/onboard", response_model=HospitalOut, status_code=201)
def onboard_hospital(
    payload: OnboardHospitalRequest,
    db: Session = Depends(db_session),
    _context: TenantContext = Depends(require_roles(UserRole.PLATFORM_ADMIN)),
):
    if db.query(User).filter(User.email == payload.admin_email).first():
        raise HTTPException(status_code=422, detail="A user with this email already exists")

    hospital = Hospital(
        name=payload.hospital_name,
        timezone=payload.timezone,
        max_concurrent_calls=payload.max_concurrent_calls,
        retry_limit=payload.retry_limit,
    )
    db.add(hospital)
    db.flush()  # get hospital.id before creating the admin user

    admin_user = User(
        hospital_id=hospital.id,
        email=payload.admin_email,
        hashed_password=hash_password(payload.admin_password),
        full_name=payload.admin_full_name,
        role=UserRole.HOSPITAL_ADMIN,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(hospital)
    return hospital


@router.get("/me", response_model=HospitalOut)
def get_my_hospital(
    db: Session = Depends(db_session),
    context: TenantContext = Depends(get_current_context),
):
    if context.hospital_id is None:
        raise HTTPException(status_code=404, detail="Current user is not scoped to a hospital")
    hospital = db.query(Hospital).filter(Hospital.id == context.hospital_id).first()
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return hospital
