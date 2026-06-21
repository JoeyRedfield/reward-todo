from datetime import date

import pytest

from app.services.task_reward_service import TaskRewardService


def _create_project_and_template(service: TaskRewardService, *, is_active: bool = True):
    project = service.create_project(name="健身")
    template = service.create_task_template(
        project_id=project.id,
        name="跑步 30 分钟",
        default_estimated_duration_minutes=30,
        default_reward_amount=2000,
        notes="晨跑",
        is_active=is_active,
    )
    return project, template


def test_complete_daily_task_creates_reward_entry(db_session) -> None:
    service = TaskRewardService(db_session)
    _, template = _create_project_and_template(service)
    task = service.create_daily_task(
        task_template_id=template.id,
        date=date(2026, 6, 20),
        estimated_duration_minutes=28,
        reward_amount=1800,
    )

    completed = service.complete_daily_task(task.id, actual_duration_minutes=26)
    summary = service.get_reward_summary(date(2026, 6, 20))
    ledger = service.list_reward_ledger()

    assert completed.status == "completed"
    assert completed.actual_duration_minutes == 26
    assert completed.completed_at is not None
    assert len(ledger) == 1
    assert ledger[0].entry_type == "earn"
    assert ledger[0].amount == 1800
    assert ledger[0].daily_task_id == task.id
    assert summary.current_balance == 1800
    assert summary.today_earned == 1800


def test_complete_daily_task_is_idempotent(db_session) -> None:
    service = TaskRewardService(db_session)
    _, template = _create_project_and_template(service)
    task = service.create_daily_task(
        task_template_id=template.id,
        date=date(2026, 6, 20),
        estimated_duration_minutes=30,
        reward_amount=2000,
    )

    service.complete_daily_task(task.id)
    service.complete_daily_task(task.id)
    ledger = service.list_reward_ledger()
    summary = service.get_reward_summary(date(2026, 6, 20))

    assert len(ledger) == 1
    assert ledger[0].amount == 2000
    assert summary.current_balance == 2000
    assert summary.today_earned == 2000


def test_reopen_daily_task_reverses_balance(db_session) -> None:
    service = TaskRewardService(db_session)
    _, template = _create_project_and_template(service)
    task = service.create_daily_task(
        task_template_id=template.id,
        date=date(2026, 6, 20),
        estimated_duration_minutes=30,
        reward_amount=2000,
    )
    service.complete_daily_task(task.id, actual_duration_minutes=29)

    reopened = service.reopen_daily_task(task.id)
    summary = service.get_reward_summary(date(2026, 6, 20))
    ledger = service.list_reward_ledger()

    assert reopened.status == "pending"
    assert reopened.actual_duration_minutes is None
    assert summary.current_balance == 0
    assert summary.today_earned == 2000
    assert [(entry.entry_type, entry.amount) for entry in ledger] == [
        ("adjust", -2000),
        ("earn", 2000),
    ]


def test_spend_reward_insufficient_balance_rejects(db_session) -> None:
    service = TaskRewardService(db_session)

    with pytest.raises(ValueError, match="余额不足"):
        service.spend_reward(amount=500, reason="咖啡")


def test_inactive_template_cannot_create_daily_task(db_session) -> None:
    service = TaskRewardService(db_session)
    _, template = _create_project_and_template(service, is_active=False)

    with pytest.raises(ValueError, match="模板已停用"):
        service.create_daily_task(
            task_template_id=template.id,
            date=date(2026, 6, 20),
            estimated_duration_minutes=30,
            reward_amount=2000,
        )


def test_update_task_template_updates_fields(db_session) -> None:
    service = TaskRewardService(db_session)
    _, template = _create_project_and_template(service)

    updated = service.update_task_template(
        template.id,
        name="夜跑 45 分钟",
        default_estimated_duration_minutes=45,
        default_reward_amount=2600,
        notes="晚间训练",
        is_active=False,
    )

    assert updated.name == "夜跑 45 分钟"
    assert updated.default_estimated_duration_minutes == 45
    assert updated.default_reward_amount == 2600
    assert updated.notes == "晚间训练"
    assert updated.is_active is False


def test_create_task_template_rejects_unknown_project_id(db_session) -> None:
    service = TaskRewardService(db_session)

    with pytest.raises(ValueError, match="项目不存在"):
        service.create_task_template(
            project_id=999999,
            name="无效模板",
            default_estimated_duration_minutes=30,
            default_reward_amount=1000,
            notes="",
            is_active=True,
        )


def test_create_daily_task_rejects_duplicate_template_for_same_date(db_session) -> None:
    service = TaskRewardService(db_session)
    _, template = _create_project_and_template(service)
    service.create_daily_task(
        task_template_id=template.id,
        date=date(2026, 6, 20),
        estimated_duration_minutes=30,
        reward_amount=2000,
    )

    with pytest.raises(ValueError, match="当日任务已存在"):
        service.create_daily_task(
            task_template_id=template.id,
            date=date(2026, 6, 20),
            estimated_duration_minutes=35,
            reward_amount=2200,
        )


def test_update_project_updates_fields(db_session) -> None:
    service = TaskRewardService(db_session)
    project = service.create_project(name="健身")

    updated = service.update_project(
        project.id,
        name="运动",
        status="archived",
        sort_order=9,
    )

    assert updated.name == "运动"
    assert updated.status == "archived"
    assert updated.sort_order == 9


def test_reward_summary_returns_current_balance_and_today_earned(db_session) -> None:
    service = TaskRewardService(db_session)
    _, template = _create_project_and_template(service)
    task = service.create_daily_task(
        task_template_id=template.id,
        date=date(2026, 6, 20),
        estimated_duration_minutes=30,
        reward_amount=2000,
    )
    service.complete_daily_task(task.id)
    service.spend_reward(amount=500, reason="兑换咖啡")

    summary = service.get_reward_summary(date(2026, 6, 20))

    assert summary.current_balance == 1500
    assert summary.today_earned == 2000


def test_reward_summary_counts_earned_by_daily_task_business_date(db_session) -> None:
    service = TaskRewardService(db_session)
    _, template = _create_project_and_template(service)
    task = service.create_daily_task(
        task_template_id=template.id,
        date=date(2026, 6, 21),
        estimated_duration_minutes=30,
        reward_amount=2000,
    )
    service.complete_daily_task(task.id)

    # Simulate a UTC-stored ledger timestamp that falls on the previous local date.
    ledger_entry = service.list_reward_ledger(limit=1)[0]
    ledger_entry.created_at = ledger_entry.created_at.replace(
        year=2026,
        month=6,
        day=20,
        hour=16,
        minute=0,
        second=0,
        microsecond=0,
    )
    db_session.commit()

    summary = service.get_reward_summary(date(2026, 6, 21))

    assert summary.current_balance == 2000
    assert summary.today_earned == 2000


def test_daily_task_snapshot_fields_are_persisted_from_template_and_payload(db_session) -> None:
    service = TaskRewardService(db_session)
    project, template = _create_project_and_template(service)

    task = service.create_daily_task(
        task_template_id=template.id,
        date=date(2026, 6, 20),
        estimated_duration_minutes=45,
        reward_amount=2500,
    )
    tasks = service.list_daily_tasks(date(2026, 6, 20))

    assert task.project_id == project.id
    assert task.task_template_id == template.id
    assert task.name_snapshot == "跑步 30 分钟"
    assert task.estimated_duration_minutes_snapshot == 45
    assert task.reward_amount_snapshot == 2500
    assert len(tasks) == 1
    assert tasks[0].name_snapshot == "跑步 30 分钟"
    assert tasks[0].reward_amount_snapshot == 2500
