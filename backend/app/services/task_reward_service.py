import datetime
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import DailyTask, RewardLedger, TaskProject, TaskTemplate, User
from app.schemas.task_reward import RewardSummaryRead


class TaskRewardService:
    ALLOWED_PROJECT_STATUSES = {"active", "archived"}

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_project(
        self,
        name: str,
        user: User,
        status: str = "active",
        sort_order: int = 0,
    ) -> TaskProject:
        normalized_name = self._normalize_required_name(name, "项目名称不能为空")
        self._validate_project_status(status)
        project = TaskProject(
            user_id=user.id,
            name=normalized_name,
            status=status,
            sort_order=sort_order,
        )
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)
        return project

    def list_projects(self, user: User) -> list[TaskProject]:
        statement = select(TaskProject).where(TaskProject.user_id == user.id)
        return self.session.scalars(
            statement.order_by(TaskProject.sort_order.asc(), TaskProject.id.asc())
        ).all()

    def update_project(
        self,
        project_id: int,
        user: User,
        **changes: object,
    ) -> TaskProject:
        project = self._get_project(project_id, user=user)
        for key, value in changes.items():
            if key == "status" and value is not None:
                self._validate_project_status(value)
            if key == "name" and value is not None:
                value = self._normalize_required_name(value, "项目名称不能为空")
            if value is not None and hasattr(project, key):
                setattr(project, key, value)
        self.session.commit()
        self.session.refresh(project)
        self.session.expunge(project)
        return project

    def create_task_template(
        self,
        project_id: int,
        name: str,
        default_estimated_duration_minutes: int,
        default_reward_amount: int,
        user: User,
        notes: str = "",
        is_active: bool = True,
    ) -> TaskTemplate:
        normalized_name = self._normalize_required_name(name, "模板名称不能为空")
        self._get_project(project_id, user=user)
        template = TaskTemplate(
            project_id=project_id,
            name=normalized_name,
            default_estimated_duration_minutes=default_estimated_duration_minutes,
            default_reward_amount=default_reward_amount,
            notes=notes,
            is_active=is_active,
        )
        self.session.add(template)
        self.session.commit()
        self.session.refresh(template)
        return template

    def update_task_template(
        self,
        template_id: int,
        user: User,
        **changes: object,
    ) -> TaskTemplate:
        template = self._get_template(template_id, user=user)
        for key, value in changes.items():
            if key == "name" and value is not None:
                value = self._normalize_required_name(value, "模板名称不能为空")
            if value is not None and hasattr(template, key):
                setattr(template, key, value)
        self.session.commit()
        self.session.refresh(template)
        self.session.expunge(template)
        return template

    def list_templates(
        self,
        user: User,
        project_id: Optional[int] = None,
    ) -> list[TaskTemplate]:
        statement = (
            select(TaskTemplate)
            .join(TaskProject, TaskTemplate.project_id == TaskProject.id)
            .where(TaskProject.user_id == user.id)
            .order_by(TaskTemplate.id.asc())
        )
        if project_id is not None:
            statement = statement.where(TaskTemplate.project_id == project_id)
        return self.session.scalars(statement).all()

    def create_daily_task(
        self,
        date: datetime.date,
        estimated_duration_minutes: int,
        reward_amount: int,
        user: User,
        task_template_id: Optional[int] = None,
        name: Optional[str] = None,
    ) -> DailyTask:
        normalized_name = self._normalize_daily_task_create_inputs(
            task_template_id=task_template_id,
            name=name,
        )

        template: Optional[TaskTemplate] = None
        project_id: Optional[int] = None
        name_snapshot: str
        template_id: Optional[int] = None

        if task_template_id is not None:
            template = self._get_template(task_template_id, user=user)
            if not template.is_active:
                raise ValueError("模板已停用")
            project_id = template.project_id
            template_id = template.id
            name_snapshot = template.name
        else:
            name_snapshot = normalized_name or ""

        task = DailyTask(
            date=date,
            user_id=user.id,
            project_id=project_id,
            task_template_id=template_id,
            name_snapshot=name_snapshot,
            estimated_duration_minutes_snapshot=estimated_duration_minutes,
            reward_amount_snapshot=reward_amount,
            status="pending",
        )
        self.session.add(task)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise ValueError("当日任务已存在")
        self.session.refresh(task)
        return task

    def delete_daily_task(self, task_id: int, user: User) -> None:
        task = self._get_daily_task(task_id, user=user)
        if task.task_template_id is not None:
            raise ValueError("只有独立任务支持删除")

        task_balance = int(
            self.session.scalar(
                select(func.coalesce(func.sum(RewardLedger.amount), 0)).where(
                    RewardLedger.daily_task_id == task.id,
                    RewardLedger.user_id == user.id,
                )
            )
            or 0
        )

        if task_balance > 0:
            self.session.add(
                RewardLedger(
                    user_id=user.id,
                    entry_type="adjust",
                    amount=-task_balance,
                    reason=f"delete:{task.name_snapshot}",
                    daily_task_id=None,
                )
            )

        self.session.query(RewardLedger).filter(
            RewardLedger.daily_task_id == task.id,
            RewardLedger.user_id == user.id,
        ).update(
            {RewardLedger.daily_task_id: None},
            synchronize_session=False,
        )
        self.session.delete(task)
        self.session.commit()

    def list_daily_tasks(self, date: datetime.date, user: User) -> list[DailyTask]:
        statement = select(DailyTask).where(
            DailyTask.date == date,
            DailyTask.user_id == user.id,
        )
        return self.session.scalars(
            statement.order_by(DailyTask.created_at.asc(), DailyTask.id.asc())
        ).all()

    def list_daily_task_calendar(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        user: User,
    ) -> list[dict[str, object]]:
        if end_date < start_date:
            raise ValueError("结束日期不能早于开始日期")

        statement = (
            select(
                DailyTask.date.label("date"),
                func.count(DailyTask.id).label("task_count"),
                func.sum(
                    case(
                        (DailyTask.status == "completed", 1),
                        else_=0,
                    )
                ).label("completed_count"),
            )
            .where(
                DailyTask.user_id == user.id,
                DailyTask.date >= start_date,
                DailyTask.date <= end_date,
            )
            .group_by(DailyTask.date)
            .order_by(DailyTask.date.asc())
        )
        rows = self.session.execute(statement).all()
        return [
            {
                "date": row.date,
                "task_count": int(row.task_count or 0),
                "completed_count": int(row.completed_count or 0),
            }
            for row in rows
        ]

    def complete_daily_task(
        self,
        task_id: int,
        user: User,
        actual_duration_minutes: Optional[int] = None,
    ) -> DailyTask:
        task = self._get_daily_task(task_id, user=user)
        if task.status == "completed":
            return task

        task_balance = self.session.scalar(
            select(func.coalesce(func.sum(RewardLedger.amount), 0)).where(
                RewardLedger.daily_task_id == task.id,
                RewardLedger.user_id == user.id,
            )
        )

        task.status = "completed"
        task.actual_duration_minutes = actual_duration_minutes
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)

        if int(task_balance or 0) <= 0:
            self.session.add(
                RewardLedger(
                    user_id=user.id,
                    entry_type="earn",
                    amount=task.reward_amount_snapshot,
                    reason=task.name_snapshot,
                    daily_task_id=task.id,
                )
            )

        self.session.commit()
        self.session.refresh(task)
        return task

    def reopen_daily_task(self, task_id: int, user: User) -> DailyTask:
        task = self._get_daily_task(task_id, user=user)
        if task.status != "completed":
            return task

        task.status = "pending"
        task.actual_duration_minutes = None
        task.completed_at = None
        self.session.add(
            RewardLedger(
                user_id=user.id,
                entry_type="adjust",
                amount=-task.reward_amount_snapshot,
                reason=f"reopen:{task.name_snapshot}",
                daily_task_id=task.id,
            )
        )
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_reward_summary(
        self,
        user: User,
        date: Optional[datetime.date] = None,
    ) -> RewardSummaryRead:
        target_date = date or datetime.date.today()
        current_balance_stmt = select(func.coalesce(func.sum(RewardLedger.amount), 0)).where(
            RewardLedger.user_id == user.id
        )
        current_balance = self.session.scalar(current_balance_stmt)

        today_earned = self.session.scalar(
            select(func.coalesce(func.sum(RewardLedger.amount), 0))
            .select_from(RewardLedger)
            .join(DailyTask, RewardLedger.daily_task_id == DailyTask.id)
            .where(
                DailyTask.date == target_date,
                RewardLedger.user_id == user.id,
            )
        )
        return RewardSummaryRead(
            current_balance=int(current_balance or 0),
            today_earned=int(today_earned or 0),
        )

    def list_reward_ledger(self, limit: int, user: User) -> list[RewardLedger]:
        statement = select(RewardLedger).where(RewardLedger.user_id == user.id)
        return self.session.scalars(
            statement.order_by(RewardLedger.created_at.desc(), RewardLedger.id.desc()).limit(limit)
        ).all()

    def spend_reward(self, amount: int, reason: str, user: User) -> RewardLedger:
        balance_stmt = select(func.coalesce(func.sum(RewardLedger.amount), 0)).where(
            RewardLedger.user_id == user.id
        )
        current_balance = self.session.scalar(balance_stmt)
        if int(current_balance or 0) < amount:
            raise ValueError("余额不足")

        entry = RewardLedger(
            user_id=user.id,
            entry_type="spend",
            amount=-amount,
            reason=reason,
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def _get_template(self, template_id: int, user: User) -> TaskTemplate:
        statement = (
            select(TaskTemplate)
            .join(TaskProject, TaskTemplate.project_id == TaskProject.id)
            .where(
                TaskTemplate.id == template_id,
                TaskProject.user_id == user.id,
            )
        )
        template = self.session.scalar(statement)
        if template is None:
            raise ValueError("任务模板不存在")
        return template

    def _get_project(self, project_id: int, user: User) -> TaskProject:
        statement = select(TaskProject).where(
            TaskProject.id == project_id,
            TaskProject.user_id == user.id,
        )
        project = self.session.scalar(statement)
        if project is None:
            raise ValueError("项目不存在")
        return project

    def _validate_project_status(self, status: str) -> None:
        if status not in self.ALLOWED_PROJECT_STATUSES:
            raise ValueError("项目状态无效")

    def _normalize_required_name(self, value: str, message: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError(message)
        return normalized

    def _normalize_daily_task_create_inputs(
        self,
        task_template_id: Optional[int],
        name: Optional[str],
    ) -> Optional[str]:
        normalized_name = name.strip() if name is not None else None
        has_template = task_template_id is not None
        has_name = normalized_name is not None and normalized_name != ""
        if has_template == has_name:
            raise ValueError("日任务创建参数无效")
        return normalized_name

    def _get_daily_task(self, task_id: int, user: User) -> DailyTask:
        statement = select(DailyTask).where(
            DailyTask.id == task_id,
            DailyTask.user_id == user.id,
        )
        task = self.session.scalar(statement)
        if task is None:
            raise ValueError("日任务不存在")
        return task
