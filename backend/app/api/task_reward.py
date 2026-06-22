import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_task_reward_service, require_authenticated_user
from app.models import User
from app.schemas.task_reward import (
    CompleteDailyTaskRequest,
    DailyTaskCalendarDayRead,
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

router = APIRouter(
    prefix="/api",
    tags=["task-reward"],
    dependencies=[Depends(require_authenticated_user)],
)


def _raise_http_error(exc: ValueError) -> None:
    raise HTTPException(status_code=400, detail=str(exc))


@router.get("/health")
async def private_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/task-projects", response_model=list[TaskProjectRead])
def list_task_projects(
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    return service.list_projects(user=user)


@router.post("/task-projects", response_model=TaskProjectRead)
def create_task_project(
    payload: TaskProjectCreate,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    return service.create_project(user=user, name=payload.name)


@router.patch("/task-projects/{project_id}", response_model=TaskProjectRead)
def update_task_project(
    project_id: int,
    payload: TaskProjectUpdate,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    try:
        return service.update_project(project_id, user=user, **payload.model_dump(exclude_none=True))
    except ValueError as exc:
        if str(exc) == "项目不存在":
            raise HTTPException(status_code=404, detail=str(exc))
        _raise_http_error(exc)


@router.get("/task-templates", response_model=list[TaskTemplateRead])
def list_task_templates(
    project_id: Optional[int] = Query(default=None),
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    return service.list_templates(user=user, project_id=project_id)


@router.post("/task-templates", response_model=TaskTemplateRead)
def create_task_template(
    payload: TaskTemplateCreate,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    try:
        return service.create_task_template(user=user, **payload.model_dump())
    except ValueError as exc:
        _raise_http_error(exc)


@router.patch("/task-templates/{template_id}", response_model=TaskTemplateRead)
def update_task_template(
    template_id: int,
    payload: TaskTemplateUpdate,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    try:
        return service.update_task_template(
            template_id,
            user=user,
            **payload.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        _raise_http_error(exc)


@router.get("/daily-tasks", response_model=list[DailyTaskRead])
def get_daily_tasks(
    date: datetime.date = Query(...),
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    return service.list_daily_tasks(date, user=user)


@router.get("/daily-tasks/calendar", response_model=list[DailyTaskCalendarDayRead])
def get_daily_task_calendar(
    start: datetime.date = Query(...),
    end: datetime.date = Query(...),
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    try:
        return service.list_daily_task_calendar(start_date=start, end_date=end, user=user)
    except ValueError as exc:
        _raise_http_error(exc)


@router.post("/daily-tasks", response_model=DailyTaskRead)
def create_daily_task(
    payload: DailyTaskCreate,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    try:
        return service.create_daily_task(user=user, **payload.model_dump())
    except ValueError as exc:
        _raise_http_error(exc)


@router.post("/daily-tasks/{task_id}/complete", response_model=DailyTaskRead)
def complete_daily_task(
    task_id: int,
    payload: CompleteDailyTaskRequest,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    try:
        return service.complete_daily_task(
            task_id,
            user=user,
            actual_duration_minutes=payload.actual_duration_minutes,
        )
    except ValueError as exc:
        _raise_http_error(exc)


@router.post("/daily-tasks/{task_id}/reopen", response_model=DailyTaskRead)
def reopen_daily_task(
    task_id: int,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    try:
        return service.reopen_daily_task(task_id, user=user)
    except ValueError as exc:
        _raise_http_error(exc)


@router.get("/rewards/summary", response_model=RewardSummaryRead)
def reward_summary(
    date: Optional[datetime.date] = Query(default=None),
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    return service.get_reward_summary(user=user, date=date)


@router.get("/rewards/ledger", response_model=list[RewardLedgerRead])
def reward_ledger(
    limit: int = Query(default=20, ge=1, le=200),
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    return service.list_reward_ledger(limit=limit, user=user)


@router.post("/rewards/spend", response_model=RewardLedgerRead)
def spend_reward(
    payload: RewardSpendRequest,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    try:
        return service.spend_reward(payload.amount, payload.reason, user=user)
    except ValueError as exc:
        _raise_http_error(exc)
