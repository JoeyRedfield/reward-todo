import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_task_reward_service, require_readonly_token
from app.schemas.public import (
    PublicLedgerResponse,
    PublicProjectsResponse,
    PublicSummaryResponse,
    PublicTemplatesResponse,
    PublicTodayResponse,
)
from app.schemas.task_reward import RewardLedgerRead, TaskProjectRead, TaskTemplateRead
from app.services.task_reward_service import TaskRewardService

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/health")
async def public_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/summary", response_model=PublicSummaryResponse)
def get_summary(
    date: datetime.date = Query(default_factory=datetime.date.today),
    _: str = Depends(require_readonly_token),
    service: TaskRewardService = Depends(get_task_reward_service),
) -> PublicSummaryResponse:
    summary = service.get_reward_summary(date)
    return PublicSummaryResponse(readOnly=True, **summary.model_dump())


@router.get("/today", response_model=PublicTodayResponse)
def get_today(
    date: datetime.date = Query(default_factory=datetime.date.today),
    _: str = Depends(require_readonly_token),
    service: TaskRewardService = Depends(get_task_reward_service),
) -> PublicTodayResponse:
    summary = service.get_reward_summary(date)
    tasks = service.list_daily_tasks(date)
    return PublicTodayResponse(readOnly=True, tasks=tasks, **summary.model_dump())


@router.get("/ledger", response_model=PublicLedgerResponse)
def get_ledger(
    limit: int = Query(default=20, ge=1, le=200),
    _: str = Depends(require_readonly_token),
    service: TaskRewardService = Depends(get_task_reward_service),
) -> PublicLedgerResponse:
    items = [RewardLedgerRead.model_validate(item) for item in service.list_reward_ledger(limit)]
    return PublicLedgerResponse(readOnly=True, items=items)


@router.get("/projects", response_model=PublicProjectsResponse)
def get_projects(
    _: str = Depends(require_readonly_token),
    service: TaskRewardService = Depends(get_task_reward_service),
) -> PublicProjectsResponse:
    items = [TaskProjectRead.model_validate(project) for project in service.list_projects()]
    return PublicProjectsResponse(readOnly=True, items=items)


@router.get("/templates", response_model=PublicTemplatesResponse)
def get_templates(
    project_id: Optional[int] = Query(default=None),
    _: str = Depends(require_readonly_token),
    service: TaskRewardService = Depends(get_task_reward_service),
) -> PublicTemplatesResponse:
    items = [
        TaskTemplateRead.model_validate(template)
        for template in service.list_templates(project_id=project_id)
    ]
    return PublicTemplatesResponse(readOnly=True, items=items)
