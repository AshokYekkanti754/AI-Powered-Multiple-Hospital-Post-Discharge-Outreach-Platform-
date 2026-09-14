import enum
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, GUID, new_uuid


class QueueTaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    CALLING = "CALLING"
    CONNECTED = "CONNECTED"
    COMPLETED = "COMPLETED"
    NO_ANSWER = "NO_ANSWER"
    BUSY = "BUSY"
    VOICEMAIL = "VOICEMAIL"
    DROPPED = "DROPPED"
    CALLBACK_SCHEDULED = "CALLBACK_SCHEDULED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    ESCALATED = "ESCALATED"
    MANUAL_FOLLOW_UP = "MANUAL_FOLLOW_UP"


class QueueTask(Base):
    __tablename__ = "queue_tasks"
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    hospital_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("hospitals.id"), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("campaigns.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=False, index=True)
    status: Mapped[QueueTaskStatus] = mapped_column(Enum(QueueTaskStatus), default=QueueTaskStatus.PENDING, nullable=False, index=True)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    call_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by_worker: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
