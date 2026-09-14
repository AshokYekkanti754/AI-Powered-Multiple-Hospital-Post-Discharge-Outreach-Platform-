import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, GUID, new_uuid


class CallOutcome(str, enum.Enum):
    COMPLETED = "COMPLETED"
    NO_ANSWER = "NO_ANSWER"
    BUSY = "BUSY"
    VOICEMAIL = "VOICEMAIL"
    DROPPED = "DROPPED"
    PATIENT_REQUESTED_CALLBACK = "PATIENT_REQUESTED_CALLBACK"
    FAILED = "FAILED"


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    queue_task_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("queue_tasks.id"), nullable=False, index=True)
    hospital_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("hospitals.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=False, index=True)
    outcome: Mapped[CallOutcome] = mapped_column(Enum(CallOutcome), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    partial_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_callback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
