from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import db_session, get_current_context
from app.core.security import create_access_token, verify_password
from app.db.models.hospital import Hospital
from app.db.models.user import User
from app.middleware.tenant import TenantContext

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    hospital_id: str | None
    hospital_name: str | None


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(db_session)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is inactive")

    token = create_access_token(
        user_id=str(user.id),
        role=user.role.value,
        hospital_id=str(user.hospital_id) if user.hospital_id else None,
    )
    return LoginResponse(access_token=token)


@router.get("/me", response_model=CurrentUserResponse)
def me(db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    user = db.query(User).filter(User.id == context.user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    hospital_name = None
    if user.hospital_id is not None:
        hospital = db.query(Hospital).filter(Hospital.id == user.hospital_id).first()
        hospital_name = hospital.name if hospital else None
    return CurrentUserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        hospital_id=str(user.hospital_id) if user.hospital_id else None,
        hospital_name=hospital_name,
    )
