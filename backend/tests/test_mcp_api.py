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


def test_mcp_returns_invalid_params_for_malformed_date(client) -> None:
    token = _create_mcp_token(
        client,
        username="reward",
        password="super-secret",
        name="bootstrap-mcp-invalid-date",
    )

    response = _mcp_call(
        client,
        token,
        "tools/call",
        params={"name": "list_daily_tasks", "arguments": {"date": "2026-99-99"}},
        request_id=9,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"]["code"] == -32602


def test_mcp_returns_invalid_params_for_non_integer_project_id(client) -> None:
    token = _create_mcp_token(
        client,
        username="reward",
        password="super-secret",
        name="bootstrap-mcp-invalid-int",
    )

    response = _mcp_call(
        client,
        token,
        "tools/call",
        params={
            "name": "create_task_template",
            "arguments": {
                "project_id": "not-an-int",
                "name": "broken",
                "default_estimated_duration_minutes": 30,
                "default_reward_amount": 10,
            },
        },
        request_id=10,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"]["code"] == -32602


def test_mcp_update_project_rejects_invalid_status(client) -> None:
    token = _create_mcp_token(
        client,
        username="reward",
        password="super-secret",
        name="bootstrap-mcp-invalid-status",
    )

    create_response = _mcp_call(
        client,
        token,
        "tools/call",
        params={"name": "create_project", "arguments": {"name": "健身"}},
        request_id=11,
    )
    assert create_response.status_code == 200
    project_id = create_response.json()["result"]["structuredContent"]["id"]

    update_response = _mcp_call(
        client,
        token,
        "tools/call",
        params={
            "name": "update_project",
            "arguments": {"project_id": project_id, "status": "paused"},
        },
        request_id=12,
    )

    assert update_response.status_code == 200
    assert update_response.json()["error"]["message"] == "项目状态无效"


def test_mcp_create_daily_task_descriptor_uses_one_of_modes(client) -> None:
    token = _create_mcp_token(
        client,
        username="reward",
        password="super-secret",
        name="bootstrap-mcp-schema-daily-task",
    )

    response = _mcp_call(
        client,
        token,
        "tools/list",
        request_id=13,
    )

    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    create_daily_task = next(tool for tool in tools if tool["name"] == "create_daily_task")
    input_schema = create_daily_task["inputSchema"]

    assert input_schema["type"] == "object"
    assert input_schema["required"] == [
        "date",
        "estimated_duration_minutes",
        "reward_amount",
    ]
    assert input_schema["oneOf"] == [
        {
            "required": ["task_template_id"],
            "not": {"required": ["name"]},
        },
        {
            "required": ["name"],
            "not": {"required": ["task_template_id"]},
        },
    ]


def test_mcp_create_daily_task_supports_standalone_mode(client) -> None:
    token = _create_mcp_token(
        client,
        username="reward",
        password="super-secret",
        name="bootstrap-mcp-standalone-task",
    )

    response = _mcp_call(
        client,
        token,
        "tools/call",
        params={
            "name": "create_daily_task",
            "arguments": {
                "name": "独立任务",
                "date": "2026-06-20",
                "estimated_duration_minutes": 35,
                "reward_amount": 1200,
            },
        },
        request_id=14,
    )

    assert response.status_code == 200
    assert response.json()["result"]["structuredContent"] == {
        "id": response.json()["result"]["structuredContent"]["id"],
        "date": "2026-06-20",
        "project_id": None,
        "task_template_id": None,
        "name_snapshot": "独立任务",
        "estimated_duration_minutes_snapshot": 35,
        "reward_amount_snapshot": 1200,
        "status": "pending",
        "actual_duration_minutes": None,
        "completed_at": None,
    }


def test_mcp_delete_daily_task_deletes_standalone_task(client) -> None:
    token = _create_mcp_token(
        client,
        username="reward",
        password="super-secret",
        name="bootstrap-mcp-delete-standalone-task",
    )

    create_response = _mcp_call(
        client,
        token,
        "tools/call",
        params={
            "name": "create_daily_task",
            "arguments": {
                "name": "可删除任务",
                "date": "2026-06-20",
                "estimated_duration_minutes": 20,
                "reward_amount": 500,
            },
        },
        request_id=15,
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["result"]["structuredContent"]["id"]

    delete_response = _mcp_call(
        client,
        token,
        "tools/call",
        params={"name": "delete_daily_task", "arguments": {"task_id": task_id}},
        request_id=16,
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["result"]["structuredContent"] == {"ok": True}

    list_response = _mcp_call(
        client,
        token,
        "tools/call",
        params={"name": "list_daily_tasks", "arguments": {"date": "2026-06-20"}},
        request_id=17,
    )
    assert list_response.status_code == 200
    assert list_response.json()["result"]["structuredContent"] == []


def test_mcp_delete_daily_task_rejects_template_based_task(client) -> None:
    token = _create_mcp_token(
        client,
        username="reward",
        password="super-secret",
        name="bootstrap-mcp-delete-template-task",
    )

    create_project_response = _mcp_call(
        client,
        token,
        "tools/call",
        params={"name": "create_project", "arguments": {"name": "健身"}},
        request_id=18,
    )
    assert create_project_response.status_code == 200
    project_id = create_project_response.json()["result"]["structuredContent"]["id"]

    create_template_response = _mcp_call(
        client,
        token,
        "tools/call",
        params={
            "name": "create_task_template",
            "arguments": {
                "project_id": project_id,
                "name": "跑步 30 分钟",
                "default_estimated_duration_minutes": 30,
                "default_reward_amount": 2000,
            },
        },
        request_id=19,
    )
    assert create_template_response.status_code == 200
    template_id = create_template_response.json()["result"]["structuredContent"]["id"]

    create_task_response = _mcp_call(
        client,
        token,
        "tools/call",
        params={
            "name": "create_daily_task",
            "arguments": {
                "task_template_id": template_id,
                "date": "2026-06-20",
                "estimated_duration_minutes": 30,
                "reward_amount": 2000,
            },
        },
        request_id=20,
    )
    assert create_task_response.status_code == 200
    task_id = create_task_response.json()["result"]["structuredContent"]["id"]

    delete_response = _mcp_call(
        client,
        token,
        "tools/call",
        params={"name": "delete_daily_task", "arguments": {"task_id": task_id}},
        request_id=21,
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["error"]["message"] == "只有独立任务支持删除"
