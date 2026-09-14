import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, GUID, new_uuid


class RiskTier(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    hospital_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("hospitals.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=False, index=True)
    discharge_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    care_setting: Mapped[str] = mapped_column(String(64), default="inpatient", nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_tier: Mapped[RiskTier] = mapped_column(Enum(RiskTier), nullable=False)
    discharge_instructions: Mapped[str] = mapped_column(String, default="", nullable=False)
    follow_up_window_hours: Mapped[int] = mapped_column(Integer, default=48, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
