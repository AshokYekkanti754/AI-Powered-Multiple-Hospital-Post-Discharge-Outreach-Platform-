import uuid
from datetime import datetime, time

from sqlalchemy import Integer, String, Time, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, GUID, new_uuid


class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    max_concurrent_calls: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    retry_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    calling_hours_start: Mapped[time] = mapped_column(Time, default=time(9, 0), nullable=False)
    calling_hours_end: Mapped[time] = mapped_column(Time, default=time(19, 0), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
