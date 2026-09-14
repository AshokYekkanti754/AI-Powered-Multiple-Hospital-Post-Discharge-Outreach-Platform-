import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import db_session, get_current_context, require_roles
from app.core.security import hash_password
from app.db.models.user import User, UserRole
from app.middleware.tenant import TenantContext

router = APIRouter()


class CreateUserRequest(BaseModel):
    email: str
    full_name: str
    password: str
    role: UserRole


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    hospital_id: uuid.UUID | None

    class Config:
        from_attributes = True


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(db_session),
    context: TenantContext = Depends(get_current_context),
):
    query = db.query(User)
    if context.role == "PLATFORM_ADMIN":
        # Platform admin may list all users; still explicit, never implicit.
        pass
    else:
        # Hard tenant filter — every non-platform-admin query is scoped.
        query = query.filter(User.hospital_id == context.hospital_id)
    return query.all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(db_session),
    context: TenantContext = Depends(require_roles(UserRole.HOSPITAL_ADMIN)),
):
    if payload.role == UserRole.PLATFORM_ADMIN:
        raise HTTPException(status_code=403, detail="Hospital admins cannot create platform admins")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=422, detail="A user with this email already exists")

    user = User(
        hospital_id=context.hospital_id,  # always inherited from context, never client-supplied
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
