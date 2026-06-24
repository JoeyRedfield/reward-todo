import datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DailyTask(Base):
    __tablename__ = "daily_tasks"
    __table_args__ = (
        Index(
            "uq_daily_task_template_date",
            "date",
            "task_template_id",
            unique=True,
            sqlite_where=text("task_template_id IS NOT NULL"),
            postgresql_where=text("task_template_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("task_projects.id"), nullable=True)
    task_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("task_templates.id"), nullable=True
    )
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

    user = relationship("User")
    template = relationship("TaskTemplate", back_populates="daily_tasks")
