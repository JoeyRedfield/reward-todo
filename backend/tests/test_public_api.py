from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import get_db_session
from app.main import create_app
from app.models import User
from app.services.task_reward_service import TaskRewardService


def _seed_data(db_session, user):
    service = TaskRewardService(db_session)
    project = service.create_project(name="健身", user=user)
    template = service.create_task_template(
        user=user,
        project_id=project.id,
        name="拉伸 15 分钟",
        default_estimated_duration_minutes=15,
        default_reward_amount=800,
        notes="晨间拉伸",
        is_active=True,
    )
    task = service.create_daily_task(
        user=user,
        task_template_id=template.id,
        date=date(2026, 6, 20),
        estimated_duration_minutes=20,
        reward_amount=1000,
    )
    service.complete_daily_task(user=user, task_id=task.id, actual_duration_minutes=18)
    return service, project, template, task


def test_public_summary_requires_token(client) -> None:
    response = client.get("/api/public/summary")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token"


def test_public_health_remains_open(client) -> None:
    response = client.get("/api/public/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_proxy_routes_mcp_requests_to_backend() -> None:
    nginx_config = (
        Path(__file__).resolve().parents[2] / "proxy" / "nginx.conf"
    ).read_text(encoding="utf-8")

    assert "location /mcp {" in nginx_config
    assert "proxy_pass http://backend:8000;" in nginx_config


def test_public_summary_rejects_invalid_token(client) -> None:
    response = client.get(
        "/api/public/summary",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid bearer token"


def test_public_summary_returns_current_balance_and_today_earned(client, db_session) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert login_response.status_code == 200
    user = db_session.scalar(select(User).where(User.username == "reward"))
    assert user is not None
    _seed_data(db_session, user=user)

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
    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert login_response.status_code == 200
    user = db_session.scalar(select(User).where(User.username == "reward"))
    assert user is not None
    _, _, _, task = _seed_data(db_session, user=user)

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
    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert login_response.status_code == 200
    user = db_session.scalar(select(User).where(User.username == "reward"))
    assert user is not None
    _seed_data(db_session, user=user)

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
    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert login_response.status_code == 200
    user = db_session.scalar(select(User).where(User.username == "reward"))
    assert user is not None
    _, project, _, _ = _seed_data(db_session, user=user)

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
    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert login_response.status_code == 200
    user = db_session.scalar(select(User).where(User.username == "reward"))
    assert user is not None
    _, _, template, _ = _seed_data(db_session, user=user)

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


def test_task_reward_endpoints_isolate_projects_tasks_and_rewards_between_users(client) -> None:
    first_register = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "display_name": "Alice",
            "email": "alice@example.com",
            "password": "alice-pass1",
            "confirm_password": "alice-pass1",
            "create_default_workspace": True,
        },
    )
    assert first_register.status_code == 200

    alice_projects = client.get("/api/task-projects")
    assert alice_projects.status_code == 200
    alice_project_ids = [item["id"] for item in alice_projects.json()]
    assert [item["name"] for item in alice_projects.json()] == ["学习", "运动", "生活"]

    alice_templates = client.get("/api/task-templates", params={"project_id": alice_project_ids[0]})
    assert alice_templates.status_code == 200
    alice_template_id = alice_templates.json()[0]["id"]

    alice_task_create = client.post(
        "/api/daily-tasks",
        json={
            "task_template_id": alice_template_id,
            "date": "2026-06-20",
            "estimated_duration_minutes": 20,
            "reward_amount": 8,
        },
    )
    assert alice_task_create.status_code == 200
    alice_task_id = alice_task_create.json()["id"]

    alice_complete = client.post(
        f"/api/daily-tasks/{alice_task_id}/complete",
        json={"actual_duration_minutes": 18},
    )
    assert alice_complete.status_code == 200

    alice_summary = client.get("/api/rewards/summary")
    assert alice_summary.status_code == 200
    assert alice_summary.json()["current_balance"] == 8

    client.post("/api/auth/logout")

    second_register = client.post(
        "/api/auth/register",
        json={
            "username": "bob",
            "display_name": "Bob",
            "email": "bob@example.com",
            "password": "bob-pass123",
            "confirm_password": "bob-pass123",
            "create_default_workspace": True,
        },
    )
    assert second_register.status_code == 200

    bob_projects = client.get("/api/task-projects")
    assert bob_projects.status_code == 200
    assert [item["name"] for item in bob_projects.json()] == ["学习", "运动", "生活"]
    assert {item["id"] for item in bob_projects.json()}.isdisjoint(set(alice_project_ids))

    bob_today = client.get("/api/daily-tasks", params={"date": "2026-06-20"})
    assert bob_today.status_code == 200
    assert bob_today.json() == []

    bob_ledger = client.get("/api/rewards/ledger")
    assert bob_ledger.status_code == 200
    assert bob_ledger.json() == []

    bob_summary = client.get("/api/rewards/summary")
    assert bob_summary.status_code == 200
    assert bob_summary.json()["current_balance"] == 0

    alice_project_response = client.patch(
        f"/api/task-projects/{alice_project_ids[0]}",
        json={"name": "非法访问"},
    )
    assert alice_project_response.status_code == 404
    assert alice_project_response.json() == {"detail": "项目不存在"}

    client.post("/api/auth/logout")
    relogin_alice = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alice-pass1"},
    )
    assert relogin_alice.status_code == 200

    alice_projects_again = client.get("/api/task-projects")
    assert alice_projects_again.status_code == 200
    assert [item["id"] for item in alice_projects_again.json()] == alice_project_ids

    alice_today = client.get("/api/daily-tasks", params={"date": "2026-06-20"})
    assert alice_today.status_code == 200
    assert len(alice_today.json()) == 1
    assert alice_today.json()[0]["id"] == alice_task_id

    alice_ledger = client.get("/api/rewards/ledger")
    assert alice_ledger.status_code == 200
    assert len(alice_ledger.json()) == 1
    assert alice_ledger.json()[0]["amount"] == 8

    alice_summary_again = client.get("/api/rewards/summary")
    assert alice_summary_again.status_code == 200
    assert alice_summary_again.json()["current_balance"] == 8


def test_public_endpoints_only_expose_bootstrap_user_data(client, db_session) -> None:
    bootstrap_login = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert bootstrap_login.status_code == 200
    bootstrap_user = db_session.scalar(select(User).where(User.username == "reward"))
    assert bootstrap_user is not None
    _, bootstrap_project, bootstrap_template, bootstrap_task = _seed_data(db_session, user=bootstrap_user)

    client.post("/api/auth/logout")
    register_response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "display_name": "Alice",
            "email": "alice@example.com",
            "password": "alice-pass1",
            "confirm_password": "alice-pass1",
            "create_default_workspace": True,
        },
    )
    assert register_response.status_code == 200

    alice_projects_response = client.get("/api/task-projects")
    assert alice_projects_response.status_code == 200
    alice_project_ids = [item["id"] for item in alice_projects_response.json()]
    alice_templates_response = client.get("/api/task-templates", params={"project_id": alice_project_ids[0]})
    assert alice_templates_response.status_code == 200
    alice_template_id = alice_templates_response.json()[0]["id"]
    alice_task_response = client.post(
        "/api/daily-tasks",
        json={
            "task_template_id": alice_template_id,
            "date": "2026-06-20",
            "estimated_duration_minutes": 20,
            "reward_amount": 8,
        },
    )
    assert alice_task_response.status_code == 200
    alice_task_id = alice_task_response.json()["id"]
    alice_complete_response = client.post(
        f"/api/daily-tasks/{alice_task_id}/complete",
        json={"actual_duration_minutes": 19},
    )
    assert alice_complete_response.status_code == 200

    summary_response = client.get(
        "/api/public/summary",
        params={"date": "2026-06-20"},
        headers={"Authorization": "Bearer readonly-test-token"},
    )
    assert summary_response.status_code == 200
    assert summary_response.json() == {
        "readOnly": True,
        "current_balance": 1000,
        "today_earned": 1000,
    }

    projects_response = client.get(
        "/api/public/projects",
        headers={"Authorization": "Bearer readonly-test-token"},
    )
    assert projects_response.status_code == 200
    assert projects_response.json()["items"] == [
        {
            "id": bootstrap_project.id,
            "name": "健身",
            "status": "active",
            "sort_order": 0,
        }
    ]

    templates_response = client.get(
        "/api/public/templates",
        headers={"Authorization": "Bearer readonly-test-token"},
    )
    assert templates_response.status_code == 200
    assert templates_response.json()["items"] == [
        {
            "id": bootstrap_template.id,
            "project_id": bootstrap_template.project_id,
            "name": "拉伸 15 分钟",
            "default_estimated_duration_minutes": 15,
            "default_reward_amount": 800,
            "notes": "晨间拉伸",
            "is_active": True,
        }
    ]

    today_response = client.get(
        "/api/public/today",
        params={"date": "2026-06-20"},
        headers={"Authorization": "Bearer readonly-test-token"},
    )
    assert today_response.status_code == 200
    assert today_response.json()["tasks"] == [
        {
            "id": bootstrap_task.id,
            "date": "2026-06-20",
            "project_id": bootstrap_task.project_id,
            "task_template_id": bootstrap_task.task_template_id,
            "name_snapshot": "拉伸 15 分钟",
            "estimated_duration_minutes_snapshot": 20,
            "reward_amount_snapshot": 1000,
            "status": "completed",
            "actual_duration_minutes": 18,
            "completed_at": bootstrap_task.completed_at.isoformat().replace("+00:00", "Z"),
        }
    ]

    ledger_response = client.get(
        "/api/public/ledger",
        headers={"Authorization": "Bearer readonly-test-token"},
    )
    assert ledger_response.status_code == 200
    assert [item["daily_task_id"] for item in ledger_response.json()["items"]] == [bootstrap_task.id]


def test_public_bootstrap_user_lookup_uses_normalized_username(db_session, monkeypatch) -> None:
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "Reward   Admin")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "super-secret")
    monkeypatch.setenv("READONLY_TOKEN", "readonly-test-token")
    get_settings.cache_clear()

    app = create_app()

    def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as isolated_client:
        login_response = isolated_client.post(
            "/api/auth/login",
            json={"username": "Reward   Admin", "password": "super-secret"},
        )
        assert login_response.status_code == 200

        create_response = isolated_client.post(
            "/api/task-projects",
            json={"name": "归一化项目"},
        )
        assert create_response.status_code == 200

        isolated_client.post("/api/auth/logout")

        public_response = isolated_client.get(
            "/api/public/projects",
            headers={"Authorization": "Bearer readonly-test-token"},
        )
        assert public_response.status_code == 200
        assert [item["name"] for item in public_response.json()["items"]] == ["归一化项目"]

    app.dependency_overrides.clear()
    get_settings.cache_clear()
