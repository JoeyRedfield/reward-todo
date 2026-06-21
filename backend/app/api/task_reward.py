import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_task_reward_service
from app.schemas.task_reward import (
    CompleteDailyTaskRequest,
    DailyTaskCreate,
    DailyTaskRead,
    RewardLedgerRead,
    RewardSpendRequest,
    RewardSummaryRead,
    TaskProjectCreate,
    TaskProjectRead,
    TaskProjectUpdate,
    TaskTemplateCreate,
    TaskTemplateRead,
    TaskTemplateUpdate,
)
from app.services.task_reward_service import TaskRewardService

router = APIRouter(prefix="/api", tags=["task-reward"])


def _raise_http_error(exc: ValueError) -> None:
    raise HTTPException(status_code=400, detail=str(exc))


@router.get("/health")
async def private_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/task-projects", response_model=list[TaskProjectRead])
def list_task_projects(service: TaskRewardService = Depends(get_task_reward_service)):
    return service.list_projects()


@router.post("/task-projects", response_model=TaskProjectRead)
def create_task_project(
    payload: TaskProjectCreate,
    service: TaskRewardService = Depends(get_task_reward_service),
):
    return service.create_project(name=payload.name)


@router.patch("/task-projects/{project_id}", response_model=TaskProjectRead)
def update_task_project(
    project_id: int,
    payload: TaskProjectUpdate,
    service: TaskRewardService = Depends(get_task_reward_service),
):
    try:
        return service.update_project(project_id, **payload.model_dump(exclude_none=True))
    except ValueError as exc:
        if str(exc) == "项目不存在":
            raise HTTPException(status_code=404, detail=str(exc))
        _raise_http_error(exc)


@router.get("/task-templates", response_model=list[TaskTemplateRead])
def list_task_templates(
    project_id: Optional[int] = Query(default=None),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    return service.list_templates(project_id=project_id)


@router.post("/task-templates", response_model=TaskTemplateRead)
def create_task_template(
    payload: TaskTemplateCreate,
    service: TaskRewardService = Depends(get_task_reward_service),
):
    try:
        return service.create_task_template(**payload.model_dump())
    except ValueError as exc:
        _raise_http_error(exc)


@router.patch("/task-templates/{template_id}", response_model=TaskTemplateRead)
def update_task_template(
    template_id: int,
    payload: TaskTemplateUpdate,
    service: TaskRewardService = Depends(get_task_reward_service),
):
    try:
        return service.update_task_template(template_id, **payload.model_dump(exclude_none=True))
    except ValueError as exc:
        _raise_http_error(exc)


@router.get("/daily-tasks", response_model=list[DailyTaskRead])
def get_daily_tasks(
    date: datetime.date = Query(...),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    return service.list_daily_tasks(date)


@router.post("/daily-tasks", response_model=DailyTaskRead)
def create_daily_task(
    payload: DailyTaskCreate,
    service: TaskRewardService = Depends(get_task_reward_service),
):
    try:
        return service.create_daily_task(**payload.model_dump())
    except ValueError as exc:
        _raise_http_error(exc)


@router.post("/daily-tasks/{task_id}/complete", response_model=DailyTaskRead)
def complete_daily_task(
    task_id: int,
    payload: CompleteDailyTaskRequest,
    service: TaskRewardService = Depends(get_task_reward_service),
):
    try:
        return service.complete_daily_task(task_id, payload.actual_duration_minutes)
    except ValueError as exc:
        _raise_http_error(exc)


@router.post("/daily-tasks/{task_id}/reopen", response_model=DailyTaskRead)
def reopen_daily_task(
    task_id: int,
    service: TaskRewardService = Depends(get_task_reward_service),
):
    try:
        return service.reopen_daily_task(task_id)
    except ValueError as exc:
        _raise_http_error(exc)


@router.get("/rewards/summary", response_model=RewardSummaryRead)
def reward_summary(service: TaskRewardService = Depends(get_task_reward_service)):
    return service.get_reward_summary(datetime.date.today())


@router.get("/rewards/ledger", response_model=list[RewardLedgerRead])
def reward_ledger(
    limit: int = Query(default=20, ge=1, le=200),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    return service.list_reward_ledger(limit)


@router.post("/rewards/spend", response_model=RewardLedgerRead)
def spend_reward(
    payload: RewardSpendRequest,
    service: TaskRewardService = Depends(get_task_reward_service),
):
    try:
        return service.spend_reward(payload.amount, payload.reason)
    except ValueError as exc:
        _raise_http_error(exc)
