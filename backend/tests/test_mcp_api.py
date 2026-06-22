import json
from typing import Optional


def _jsonrpc_request(method: str, *, params: Optional[dict] = None, request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }


def _create_mcp_token(client, *, username: str, password: str, name: str) -> str:
    login_response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert login_response.status_code == 200

    token_response = client.post(
        "/api/account/tokens",
        json={
            "name": name,
            "token_type": "mcp",
            "password": password,
            "expires_in_days": 30,
        },
    )
    assert token_response.status_code == 201
    return token_response.json()["token"]


def _mcp_call(client, token: str, method: str, *, params: Optional[dict] = None, request_id: int = 1):
    return client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {token}"},
        json=_jsonrpc_request(method, params=params, request_id=request_id),
    )


def test_mcp_token_is_limited_to_own_task_reward_data(client) -> None:
    bootstrap_token = _create_mcp_token(
        client,
        username="reward",
        password="super-secret",
        name="bootstrap-mcp",
    )

    bootstrap_create_project = _mcp_call(
        client,
        bootstrap_token,
        "tools/call",
        params={"name": "create_project", "arguments": {"name": "Bootstrap Project"}},
    )
    assert bootstrap_create_project.status_code == 200
    bootstrap_project = bootstrap_create_project.json()["result"]["structuredContent"]
    bootstrap_project_id = bootstrap_project["id"]

    bootstrap_create_template = _mcp_call(
        client,
        bootstrap_token,
        "tools/call",
        params={
            "name": "create_task_template",
            "arguments": {
                "project_id": bootstrap_project_id,
                "name": "Bootstrap Template",
                "default_estimated_duration_minutes": 25,
                "default_reward_amount": 11,
                "notes": "",
                "is_active": True,
            },
        },
        request_id=2,
    )
    assert bootstrap_create_template.status_code == 200
    bootstrap_template_id = bootstrap_create_template.json()["result"]["structuredContent"]["id"]

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

    alice_token = _create_mcp_token(
        client,
        username="alice",
        password="alice-pass1",
        name="alice-mcp",
    )

    alice_projects_response = _mcp_call(
        client,
        alice_token,
        "resources/read",
        params={"uri": "reward-todo://projects"},
        request_id=3,
    )
    assert alice_projects_response.status_code == 200
    alice_projects_payload = json.loads(
        alice_projects_response.json()["result"]["contents"][0]["text"]
    )
    assert [item["name"] for item in alice_projects_payload] == ["学习", "运动", "生活"]
    assert all(item["name"] != "Bootstrap Project" for item in alice_projects_payload)

    bootstrap_projects_response = _mcp_call(
        client,
        bootstrap_token,
        "resources/read",
        params={"uri": "reward-todo://projects"},
        request_id=4,
    )
    assert bootstrap_projects_response.status_code == 200
    bootstrap_projects_payload = json.loads(
        bootstrap_projects_response.json()["result"]["contents"][0]["text"]
    )
    assert [item["name"] for item in bootstrap_projects_payload] == ["Bootstrap Project"]

    alice_templates_response = _mcp_call(
        client,
        alice_token,
        "tools/call",
        params={"name": "list_task_templates", "arguments": {"project_id": bootstrap_project_id}},
        request_id=5,
    )
    assert alice_templates_response.status_code == 200
    assert alice_templates_response.json()["result"]["structuredContent"] == []

    alice_update_project = _mcp_call(
        client,
        alice_token,
        "tools/call",
        params={
            "name": "update_project",
            "arguments": {"project_id": bootstrap_project_id, "name": "stolen"},
        },
        request_id=6,
    )
    assert alice_update_project.status_code == 200
    assert alice_update_project.json()["error"]["message"] == "项目不存在"

    alice_create_task = _mcp_call(
        client,
        alice_token,
        "tools/call",
        params={
            "name": "create_daily_task",
            "arguments": {
                "task_template_id": bootstrap_template_id,
                "date": "2026-06-20",
                "estimated_duration_minutes": 25,
                "reward_amount": 11,
            },
        },
        request_id=7,
    )
    assert alice_create_task.status_code == 200
    assert alice_create_task.json()["error"]["message"] == "任务模板不存在"

    alice_summary_response = _mcp_call(
        client,
        alice_token,
        "tools/call",
        params={"name": "get_reward_summary", "arguments": {"date": "2026-06-20"}},
        request_id=8,
    )
    assert alice_summary_response.status_code == 200
    assert alice_summary_response.json()["result"]["structuredContent"] == {
        "current_balance": 0,
        "today_earned": 0,
    }
