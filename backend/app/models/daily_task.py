import datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DailyTask(Base):
    __tablename__ = "daily_tasks"
    __table_args__ = (
        UniqueConstraint("date", "task_template_id", name="uq_daily_task_template_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    project_id: Mapped[int] = mapped_column(ForeignKey("task_projects.id"))
    task_template_id: Mapped[int] = mapped_column(ForeignKey("task_templates.id"))
    name_snapshot: Mapped[str] = mapped_column(String(200))
    estimated_duration_minutes_snapshot: Mapped[int] = mapped_column(Integer)
    reward_amount_snapshot: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    actual_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template = relationship("TaskTemplate", back_populates="daily_tasks")
