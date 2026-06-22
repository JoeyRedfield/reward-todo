import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import DailyTask, RewardLedger, TaskProject, TaskTemplate, User
from app.schemas.task_reward import RewardSummaryRead


class TaskRewardService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_project(
        self,
        name: str,
        user: Optional[User] = None,
        status: str = "active",
        sort_order: int = 0,
    ) -> TaskProject:
        project = TaskProject(
            user_id=user.id if user is not None else None,
            name=name,
            status=status,
            sort_order=sort_order,
        )
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)
        return project

    def list_projects(self, user: Optional[User] = None) -> list[TaskProject]:
        statement = select(TaskProject)
        if user is not None:
            statement = statement.where(TaskProject.user_id == user.id)
        return self.session.scalars(
            statement.order_by(TaskProject.sort_order.asc(), TaskProject.id.asc())
        ).all()

    def update_project(
        self,
        project_id: int,
        user: Optional[User] = None,
        **changes: object,
    ) -> TaskProject:
        project = self._get_project(project_id, user=user)
        for key, value in changes.items():
            if value is not None and hasattr(project, key):
                setattr(project, key, value)
        self.session.commit()
        self.session.refresh(project)
        return project

    def create_task_template(
        self,
        project_id: int,
        name: str,
        default_estimated_duration_minutes: int,
        default_reward_amount: int,
        user: Optional[User] = None,
        notes: str = "",
        is_active: bool = True,
    ) -> TaskTemplate:
        self._get_project(project_id, user=user)
        template = TaskTemplate(
            project_id=project_id,
            name=name,
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
        user: Optional[User] = None,
        **changes: object,
    ) -> TaskTemplate:
        template = self._get_template(template_id, user=user)
        for key, value in changes.items():
            if value is not None and hasattr(template, key):
                setattr(template, key, value)
        self.session.commit()
        self.session.refresh(template)
        return template

    def list_templates(
        self,
        project_id: Optional[int] = None,
        user: Optional[User] = None,
    ) -> list[TaskTemplate]:
        statement = select(TaskTemplate).order_by(TaskTemplate.id.asc())
        if user is not None:
            statement = statement.join(TaskProject, TaskTemplate.project_id == TaskProject.id).where(
                TaskProject.user_id == user.id
            )
        if project_id is not None:
            statement = statement.where(TaskTemplate.project_id == project_id)
        return self.session.scalars(statement).all()

    def create_daily_task(
        self,
        task_template_id: int,
        date: datetime.date,
        estimated_duration_minutes: int,
        reward_amount: int,
        user: Optional[User] = None,
    ) -> DailyTask:
        template = self._get_template(task_template_id, user=user)
        if not template.is_active:
            raise ValueError("模板已停用")

        task = DailyTask(
            date=date,
            user_id=user.id if user is not None else None,
            project_id=template.project_id,
            task_template_id=template.id,
            name_snapshot=template.name,
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

    def list_daily_tasks(self, date: datetime.date, user: Optional[User] = None) -> list[DailyTask]:
        statement = select(DailyTask).where(DailyTask.date == date)
        if user is not None:
            statement = statement.where(DailyTask.user_id == user.id)
        return self.session.scalars(
            statement.order_by(DailyTask.created_at.asc(), DailyTask.id.asc())
        ).all()

    def complete_daily_task(
        self,
        task_id: int,
        user: Optional[User] = None,
        actual_duration_minutes: Optional[int] = None,
    ) -> DailyTask:
        task = self._get_daily_task(task_id, user=user)
        if task.status == "completed":
            return task

        task_balance = self.session.scalar(
            select(func.coalesce(func.sum(RewardLedger.amount), 0)).where(
                RewardLedger.daily_task_id == task.id,
                *((RewardLedger.user_id == user.id,) if user is not None else ()),
            )
        )

        task.status = "completed"
        task.actual_duration_minutes = actual_duration_minutes
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)

        if int(task_balance or 0) <= 0:
            self.session.add(
                RewardLedger(
                    user_id=user.id if user is not None else None,
                    entry_type="earn",
                    amount=task.reward_amount_snapshot,
                    reason=task.name_snapshot,
                    daily_task_id=task.id,
                )
            )

        self.session.commit()
        self.session.refresh(task)
        return task

    def reopen_daily_task(self, task_id: int, user: Optional[User] = None) -> DailyTask:
        task = self._get_daily_task(task_id, user=user)
        if task.status != "completed":
            return task

        task.status = "pending"
        task.actual_duration_minutes = None
        task.completed_at = None
        self.session.add(
            RewardLedger(
                user_id=user.id if user is not None else None,
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
        date: Optional[datetime.date] = None,
        user: Optional[User] = None,
    ) -> RewardSummaryRead:
        target_date = date or datetime.date.today()
        current_balance_stmt = select(func.coalesce(func.sum(RewardLedger.amount), 0))
        if user is not None:
            current_balance_stmt = current_balance_stmt.where(RewardLedger.user_id == user.id)
        current_balance = self.session.scalar(current_balance_stmt)

        today_earned = self.session.scalar(
            select(func.coalesce(func.sum(RewardLedger.amount), 0))
            .select_from(RewardLedger)
            .join(DailyTask, RewardLedger.daily_task_id == DailyTask.id)
            .where(
                RewardLedger.entry_type == "earn",
                DailyTask.date == target_date,
                *((RewardLedger.user_id == user.id,) if user is not None else ()),
            )
        )
        return RewardSummaryRead(
            current_balance=int(current_balance or 0),
            today_earned=int(today_earned or 0),
        )

    def list_reward_ledger(self, limit: int = 20, user: Optional[User] = None) -> list[RewardLedger]:
        statement = select(RewardLedger)
        if user is not None:
            statement = statement.where(RewardLedger.user_id == user.id)
        return self.session.scalars(
            statement.order_by(RewardLedger.created_at.desc(), RewardLedger.id.desc()).limit(limit)
        ).all()

    def spend_reward(self, amount: int, reason: str, user: Optional[User] = None) -> RewardLedger:
        balance_stmt = select(func.coalesce(func.sum(RewardLedger.amount), 0))
        if user is not None:
            balance_stmt = balance_stmt.where(RewardLedger.user_id == user.id)
        current_balance = self.session.scalar(balance_stmt)
        if int(current_balance or 0) < amount:
            raise ValueError("余额不足")

        entry = RewardLedger(
            user_id=user.id if user is not None else None,
            entry_type="spend",
            amount=-amount,
            reason=reason,
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def _get_template(self, template_id: int, user: Optional[User] = None) -> TaskTemplate:
        statement = select(TaskTemplate).where(TaskTemplate.id == template_id)
        if user is not None:
            statement = statement.join(TaskProject, TaskTemplate.project_id == TaskProject.id).where(
                TaskProject.user_id == user.id
            )
        template = self.session.scalar(statement)
        if template is None:
            raise ValueError("任务模板不存在")
        return template

    def _get_project(self, project_id: int, user: Optional[User] = None) -> TaskProject:
        statement = select(TaskProject).where(TaskProject.id == project_id)
        if user is not None:
            statement = statement.where(TaskProject.user_id == user.id)
        project = self.session.scalar(statement)
        if project is None:
            raise ValueError("项目不存在")
        return project

    def _get_daily_task(self, task_id: int, user: Optional[User] = None) -> DailyTask:
        statement = select(DailyTask).where(DailyTask.id == task_id)
        if user is not None:
            statement = statement.where(DailyTask.user_id == user.id)
        task = self.session.scalar(statement)
        if task is None:
            raise ValueError("日任务不存在")
        return task
