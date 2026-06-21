from datetime import date

from app.services.task_reward_service import TaskRewardService


def _seed_data(db_session):
    service = TaskRewardService(db_session)
    project = service.create_project(name="健身")
    template = service.create_task_template(
        project_id=project.id,
        name="拉伸 15 分钟",
        default_estimated_duration_minutes=15,
        default_reward_amount=800,
        notes="晨间拉伸",
        is_active=True,
    )
    task = service.create_daily_task(
        task_template_id=template.id,
        date=date(2026, 6, 20),
        estimated_duration_minutes=20,
        reward_amount=1000,
    )
    service.complete_daily_task(task.id, actual_duration_minutes=18)
    return service, project, template, task


def test_public_summary_requires_token(client) -> None:
    response = client.get("/api/public/summary")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token"


def test_public_health_remains_open(client) -> None:
    response = client.get("/api/public/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_public_summary_rejects_invalid_token(client) -> None:
    response = client.get(
        "/api/public/summary",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid bearer token"


def test_public_summary_returns_current_balance_and_today_earned(client, db_session) -> None:
    _seed_data(db_session)

    response = client.get(
        "/api/public/summary",
        params={"date": "2026-06-20"},
        headers={"Authorization": "Bearer readonly-test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "readOnly": True,
        "current_balance": 1000,
        "today_earned": 1000,
    }


def test_public_today_returns_snapshot_based_task_payload(client, db_session) -> None:
    _, _, _, task = _seed_data(db_session)

    response = client.get(
        "/api/public/today",
        params={"date": "2026-06-20"},
        headers={"Authorization": "Bearer readonly-test-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["readOnly"] is True
    assert payload["current_balance"] == 1000
    assert payload["today_earned"] == 1000
    assert payload["tasks"] == [
        {
            "id": task.id,
            "date": "2026-06-20",
            "project_id": task.project_id,
            "task_template_id": task.task_template_id,
            "name_snapshot": "拉伸 15 分钟",
            "estimated_duration_minutes_snapshot": 20,
            "reward_amount_snapshot": 1000,
            "status": "completed",
            "actual_duration_minutes": 18,
            "completed_at": task.completed_at.isoformat().replace("+00:00", "Z"),
        }
    ]


def test_public_ledger_returns_happy_path_payload(client, db_session) -> None:
    _seed_data(db_session)

    response = client.get(
        "/api/public/ledger",
        headers={"Authorization": "Bearer readonly-test-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["readOnly"] is True
    assert len(payload["items"]) == 1
    assert payload["items"][0]["entry_type"] == "earn"
    assert payload["items"][0]["amount"] == 1000
    assert payload["items"][0]["reason"] == "拉伸 15 分钟"


def test_public_projects_returns_happy_path_payload(client, db_session) -> None:
    _, project, _, _ = _seed_data(db_session)

    response = client.get(
        "/api/public/projects",
        headers={"Authorization": "Bearer readonly-test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "readOnly": True,
        "items": [
            {
                "id": project.id,
                "name": "健身",
                "status": "active",
                "sort_order": 0,
            }
        ],
    }


def test_public_templates_returns_happy_path_payload(client, db_session) -> None:
    _, _, template, _ = _seed_data(db_session)

    response = client.get(
        "/api/public/templates",
        headers={"Authorization": "Bearer readonly-test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "readOnly": True,
        "items": [
            {
                "id": template.id,
                "project_id": template.project_id,
                "name": "拉伸 15 分钟",
                "default_estimated_duration_minutes": 15,
                "default_reward_amount": 800,
                "notes": "晨间拉伸",
                "is_active": True,
            }
        ],
    }


def test_private_create_task_template_rejects_unknown_project_id(client) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert login_response.status_code == 200

    response = client.post(
        "/api/task-templates",
        json={
            "project_id": 999999,
            "name": "无效模板",
            "default_estimated_duration_minutes": 30,
            "default_reward_amount": 1000,
            "notes": "",
            "is_active": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "项目不存在"
