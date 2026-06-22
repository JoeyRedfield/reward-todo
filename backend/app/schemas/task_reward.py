from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class TaskProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TaskProjectCreate(TaskProjectBase):
    pass


class TaskProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    status: Optional[str] = None
    sort_order: Optional[int] = None


class TaskProjectRead(BaseModel):
    id: int
    name: str
    status: str
    sort_order: int

    model_config = {"from_attributes": True}


class TaskTemplateCreate(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=200)
    default_estimated_duration_minutes: int = Field(ge=1, le=1440)
    default_reward_amount: int = Field(ge=0)
    notes: str = ""
    is_active: bool = True


class TaskTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    default_estimated_duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    default_reward_amount: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class TaskTemplateRead(BaseModel):
    id: int
    project_id: int
    name: str
    default_estimated_duration_minutes: int
    default_reward_amount: int
    notes: str
    is_active: bool

    model_config = {"from_attributes": True}


class DailyTaskCreate(BaseModel):
    date: date
    task_template_id: int
    estimated_duration_minutes: int = Field(ge=1, le=1440)
    reward_amount: int = Field(ge=0)


class DailyTaskUpdate(BaseModel):
    name_snapshot: Optional[str] = Field(default=None, min_length=1, max_length=200)
    estimated_duration_minutes_snapshot: Optional[int] = Field(default=None, ge=1, le=1440)
    reward_amount_snapshot: Optional[int] = Field(default=None, ge=0)


class CompleteDailyTaskRequest(BaseModel):
    actual_duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)


class DailyTaskRead(BaseModel):
    id: int
    date: date
    project_id: int
    task_template_id: int
    name_snapshot: str
    estimated_duration_minutes_snapshot: int
    reward_amount_snapshot: int
    status: str
    actual_duration_minutes: Optional[int]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DailyTaskCalendarDayRead(BaseModel):
    date: date
    task_count: int
    completed_count: int


class RewardSummaryRead(BaseModel):
    current_balance: int
    today_earned: int


class RewardSpendRequest(BaseModel):
    amount: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


class RewardLedgerRead(BaseModel):
    id: int
    entry_type: str
    amount: int
    reason: str
    daily_task_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}
