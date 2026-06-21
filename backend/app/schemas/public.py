from pydantic import BaseModel

from app.schemas.task_reward import (
    DailyTaskRead,
    RewardLedgerRead,
    RewardSummaryRead,
    TaskProjectRead,
    TaskTemplateRead,
)


class PublicTodayResponse(RewardSummaryRead):
    readOnly: bool
    tasks: list[DailyTaskRead]


class PublicSummaryResponse(RewardSummaryRead):
    readOnly: bool


class PublicLedgerResponse(BaseModel):
    readOnly: bool
    items: list[RewardLedgerRead]


class PublicProjectsResponse(BaseModel):
    readOnly: bool
    items: list[TaskProjectRead]


class PublicTemplatesResponse(BaseModel):
    readOnly: bool
    items: list[TaskTemplateRead]
