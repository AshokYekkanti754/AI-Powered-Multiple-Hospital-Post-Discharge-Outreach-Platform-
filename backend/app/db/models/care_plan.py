import uuid
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, GUID, new_uuid


class CarePlan(Base):
    __tablename__ = "care_plans"
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    patient_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("encounters.id"), nullable=False)
    goal: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
