import uuid
from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, GUID, new_uuid


class SafetyEvalRun(Base):
    __tablename__ = "safety_eval_runs"
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    run_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    true_positives: Mapped[int] = mapped_column(Integer, nullable=False)
    false_positives: Mapped[int] = mapped_column(Integer, nullable=False)
    true_negatives: Mapped[int] = mapped_column(Integer, nullable=False)
    false_negatives: Mapped[int] = mapped_column(Integer, nullable=False)
    false_negative_rate: Mapped[float] = mapped_column(Float, nullable=False)
    report_markdown: Mapped[str] = mapped_column(Text, nullable=False)
