import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, GUID, new_uuid


class EscalationStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"


class EscalationSeverity(str, enum.Enum):
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    hospital_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("hospitals.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("campaigns.id"), nullable=False, index=True)
    call_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("calls.id"), nullable=True)
    status: Mapped[EscalationStatus] = mapped_column(Enum(EscalationStatus), default=EscalationStatus.OPEN, nullable=False, index=True)
    severity: Mapped[EscalationSeverity] = mapped_column(Enum(EscalationSeverity), nullable=False, index=True)
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # REQ-2: set True when the 15-minute timeout worker elevates an unacknowledged escalation.
    timeout_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
