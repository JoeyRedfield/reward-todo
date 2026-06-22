import json
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import get_task_reward_service, require_mcp_access_token
from app.models import User
from app.schemas.task_reward import (
    DailyTaskRead,
    RewardLedgerRead,
    RewardSummaryRead,
    TaskProjectRead,
    TaskTemplateRead,
)
from app.services.task_reward_service import TaskRewardService

router = APIRouter(prefix="/mcp", tags=["mcp"])

SUPPORTED_PROTOCOL_VERSIONS = {"2025-06-18", "2025-03-26", "2024-11-05"}
LATEST_PROTOCOL_VERSION = "2025-06-18"


def _jsonrpc_result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id, code: int, message: str):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_descriptor(name: str, description: str, input_schema: dict, output_schema: dict):
    return {
        "name": name,
        "description": description,
        "inputSchema": input_schema,
        "outputSchema": output_schema,
    }


def _text_result(structured_content):
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(structured_content, ensure_ascii=False, default=str),
            }
        ],
        "structuredContent": structured_content,
        "isError": False,
    }


def _resource_descriptor(uri: str, name: str, description: str):
    return {
        "uri": uri,
        "name": name,
        "title": name,
        "description": description,
        "mimeType": "application/json",
    }


def _resource_read_result(uri: str, payload):
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(payload, ensure_ascii=False, default=str),
            }
        ]
    }


def _invalid_params(request_id, message: str):
    return _jsonrpc_error(request_id, -32602, message)


def _require_arguments(request_id, arguments: Any):
    if not isinstance(arguments, dict):
        return None, _invalid_params(request_id, "Invalid params: arguments must be an object")
    return arguments, None


def _parse_date_argument(request_id, value, field_name: str):
    try:
        return date.fromisoformat(value), None
    except (TypeError, ValueError):
        return None, _invalid_params(request_id, f"Invalid params: {field_name} must be a valid date")


def _parse_int_argument(request_id, value, field_name: str):
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, _invalid_params(request_id, f"Invalid params: {field_name} must be an integer")


@router.post("")
async def handle_mcp(
    request: Request,
    authenticated: tuple[User, str] = Depends(require_mcp_access_token),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    _user, _ = authenticated
    payload = await request.json()
    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if method == "initialize":
        requested_version = params.get("protocolVersion")
        protocol_version = (
            requested_version if requested_version in SUPPORTED_PROTOCOL_VERSIONS else LATEST_PROTOCOL_VERSION
        )
        return _jsonrpc_result(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {
                    "resources": {"subscribe": False, "listChanged": False},
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "reward-todo-mcp",
                    "title": "Reward Todo",
                    "version": "0.1.0",
                },
            },
        )

    if method == "resources/list":
        return _jsonrpc_result(
            request_id,
            {
                "resources": [
                    _resource_descriptor(
                        "reward-todo://projects",
                        "Task Projects",
                        "Current task project list.",
                    ),
                    _resource_descriptor(
                        "reward-todo://daily-tasks/today",
                        "Today Tasks",
                        "Today daily task snapshot.",
                    ),
                    _resource_descriptor(
                        "reward-todo://reward-summary/today",
                        "Today Reward Summary",
                        "Current balance and today's earned rewards.",
                    ),
                    _resource_descriptor(
                        "reward-todo://reward-ledger/recent",
                        "Recent Reward Ledger",
                        "Recent reward ledger entries.",
                    ),
                    _resource_descriptor(
                        "reward-todo://account/profile",
                        "Account Profile",
                        "Current authenticated account profile.",
                    ),
                ]
            },
        )

    if method == "resources/read":
        resource_uri = params.get("uri")

        if resource_uri == "reward-todo://projects":
            payload = [
                TaskProjectRead.model_validate(item).model_dump()
                for item in service.list_projects(user=_user)
            ]
            return _jsonrpc_result(request_id, _resource_read_result(resource_uri, payload))

        if resource_uri == "reward-todo://daily-tasks/today":
            payload = [
                DailyTaskRead.model_validate(item).model_dump()
                for item in service.list_daily_tasks(date.today(), user=_user)
            ]
            return _jsonrpc_result(request_id, _resource_read_result(resource_uri, payload))

        if resource_uri == "reward-todo://reward-summary/today":
            payload = RewardSummaryRead.model_validate(
                service.get_reward_summary(user=_user, date=date.today())
            ).model_dump()
            return _jsonrpc_result(request_id, _resource_read_result(resource_uri, payload))

        if resource_uri == "reward-todo://reward-ledger/recent":
            payload = [
                RewardLedgerRead.model_validate(item).model_dump()
                for item in service.list_reward_ledger(limit=20, user=_user)
            ]
            return _jsonrpc_result(request_id, _resource_read_result(resource_uri, payload))

        if resource_uri == "reward-todo://account/profile":
            user_payload = {
                "id": _user.id,
                "username": _user.username,
                "created_at": _user.created_at,
                "password_changed_at": _user.password_changed_at,
                "last_login_at": _user.last_login_at,
            }
            return _jsonrpc_result(request_id, _resource_read_result(resource_uri, user_payload))

        return _jsonrpc_error(request_id, -32601, "Resource not found")

    if method == "tools/list":
        return _jsonrpc_result(
            request_id,
            {
                "tools": [
                    _tool_descriptor(
                        "get_reward_summary",
                        "Get reward balance and today's earned amount.",
                        {
                            "type": "object",
                            "properties": {"date": {"type": "string", "format": "date"}},
                        },
                        {
                            "type": "object",
                            "properties": {
                                "current_balance": {"type": "integer"},
                                "today_earned": {"type": "integer"},
                            },
                            "required": ["current_balance", "today_earned"],
                        },
                    ),
                    _tool_descriptor(
                        "list_task_projects",
                        "List all task projects for the current user.",
                        {"type": "object"},
                        {"type": "array"},
                    ),
                    _tool_descriptor(
                        "list_daily_tasks",
                        "List daily tasks by date.",
                        {
                            "type": "object",
                            "properties": {"date": {"type": "string", "format": "date"}},
                            "required": ["date"],
                        },
                        {"type": "array"},
                    ),
                    _tool_descriptor(
                        "list_task_templates",
                        "List task templates, optionally filtered by project.",
                        {
                            "type": "object",
                            "properties": {"project_id": {"type": "integer"}},
                        },
                        {"type": "array"},
                    ),
                    _tool_descriptor(
                        "list_reward_ledger",
                        "List recent reward ledger entries.",
                        {
                            "type": "object",
                            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                        },
                        {"type": "array"},
                    ),
                    _tool_descriptor(
                        "create_project",
                        "Create a task project.",
                        {
                            "type": "object",
                            "properties": {"name": {"type": "string"}},
                            "required": ["name"],
                        },
                        {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "status": {"type": "string"},
                                "sort_order": {"type": "integer"},
                            },
                        },
                    ),
                    _tool_descriptor(
                        "update_project",
                        "Update a task project.",
                        {
                            "type": "object",
                            "properties": {
                                "project_id": {"type": "integer"},
                                "name": {"type": "string"},
                                "status": {"type": "string"},
                                "sort_order": {"type": "integer"},
                            },
                            "required": ["project_id"],
                        },
                        {"type": "object"},
                    ),
                    _tool_descriptor(
                        "create_task_template",
                        "Create a task template.",
                        {
                            "type": "object",
                            "properties": {
                                "project_id": {"type": "integer"},
                                "name": {"type": "string"},
                                "default_estimated_duration_minutes": {"type": "integer"},
                                "default_reward_amount": {"type": "integer"},
                                "notes": {"type": "string"},
                                "is_active": {"type": "boolean"},
                            },
                            "required": [
                                "project_id",
                                "name",
                                "default_estimated_duration_minutes",
                                "default_reward_amount",
                            ],
                        },
                        {"type": "object"},
                    ),
                    _tool_descriptor(
                        "update_task_template",
                        "Update a task template.",
                        {
                            "type": "object",
                            "properties": {
                                "template_id": {"type": "integer"},
                                "name": {"type": "string"},
                                "default_estimated_duration_minutes": {"type": "integer"},
                                "default_reward_amount": {"type": "integer"},
                                "notes": {"type": "string"},
                                "is_active": {"type": "boolean"},
                            },
                            "required": ["template_id"],
                        },
                        {"type": "object"},
                    ),
                    _tool_descriptor(
                        "create_daily_task",
                        "Create a daily task from an existing template.",
                        {
                            "type": "object",
                            "properties": {
                                "task_template_id": {"type": "integer"},
                                "date": {"type": "string", "format": "date"},
                                "estimated_duration_minutes": {"type": "integer"},
                                "reward_amount": {"type": "integer"},
                            },
                            "required": [
                                "task_template_id",
                                "date",
                                "estimated_duration_minutes",
                                "reward_amount",
                            ],
                        },
                        {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "date": {"type": "string"},
                                "project_id": {"type": "integer"},
                                "task_template_id": {"type": "integer"},
                                "name_snapshot": {"type": "string"},
                                "estimated_duration_minutes_snapshot": {"type": "integer"},
                                "reward_amount_snapshot": {"type": "integer"},
                                "status": {"type": "string"},
                            },
                        },
                    ),
                    _tool_descriptor(
                        "complete_daily_task",
                        "Complete a daily task and optionally record actual duration.",
                        {
                            "type": "object",
                            "properties": {
                                "task_id": {"type": "integer"},
                                "actual_duration_minutes": {"type": "integer"},
                            },
                            "required": ["task_id"],
                        },
                        {"type": "object"},
                    ),
                    _tool_descriptor(
                        "reopen_daily_task",
                        "Reopen a completed daily task.",
                        {
                            "type": "object",
                            "properties": {
                                "task_id": {"type": "integer"},
                            },
                            "required": ["task_id"],
                        },
                        {"type": "object"},
                    ),
                    _tool_descriptor(
                        "spend_reward",
                        "Spend reward balance and write a ledger entry.",
                        {
                            "type": "object",
                            "properties": {
                                "amount": {"type": "integer"},
                                "reason": {"type": "string"},
                            },
                            "required": ["amount", "reason"],
                        },
                        {"type": "object"},
                    ),
                ]
            },
        )

    if method == "tools/call":
        tool_name = params.get("name")
        arguments, invalid_response = _require_arguments(request_id, params.get("arguments") or {})
        if invalid_response is not None:
            return invalid_response

        if tool_name == "get_reward_summary":
            if arguments.get("date"):
                target_date, invalid_response = _parse_date_argument(request_id, arguments["date"], "date")
                if invalid_response is not None:
                    return invalid_response
            else:
                target_date = date.today()
            result = RewardSummaryRead.model_validate(
                service.get_reward_summary(user=_user, date=target_date)
            ).model_dump()
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "list_task_projects":
            result = [
                TaskProjectRead.model_validate(item).model_dump()
                for item in service.list_projects(user=_user)
            ]
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "list_daily_tasks":
            if "date" not in arguments:
                return _invalid_params(request_id, "Missing required argument: date")
            target_date, invalid_response = _parse_date_argument(request_id, arguments["date"], "date")
            if invalid_response is not None:
                return invalid_response
            result = [
                DailyTaskRead.model_validate(item).model_dump()
                for item in service.list_daily_tasks(target_date, user=_user)
            ]
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "list_task_templates":
            project_id = arguments.get("project_id")
            parsed_project_id = None
            if project_id is not None:
                parsed_project_id, invalid_response = _parse_int_argument(
                    request_id,
                    project_id,
                    "project_id",
                )
                if invalid_response is not None:
                    return invalid_response
            result = [
                TaskTemplateRead.model_validate(item).model_dump()
                for item in service.list_templates(
                    user=_user,
                    project_id=parsed_project_id,
                )
            ]
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "list_reward_ledger":
            limit, invalid_response = _parse_int_argument(
                request_id,
                arguments.get("limit", 20),
                "limit",
            )
            if invalid_response is not None:
                return invalid_response
            result = [
                RewardLedgerRead.model_validate(item).model_dump()
                for item in service.list_reward_ledger(limit=limit, user=_user)
            ]
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "create_project":
            if not arguments.get("name"):
                return _invalid_params(request_id, "Missing required argument: name")
            result = TaskProjectRead.model_validate(
                service.create_project(arguments["name"], user=_user)
            ).model_dump()
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "update_project":
            if "project_id" not in arguments:
                return _invalid_params(request_id, "Missing required argument: project_id")
            project_id, invalid_response = _parse_int_argument(
                request_id,
                arguments["project_id"],
                "project_id",
            )
            if invalid_response is not None:
                return invalid_response
            sort_order = None
            if arguments.get("sort_order") is not None:
                sort_order, invalid_response = _parse_int_argument(
                    request_id,
                    arguments["sort_order"],
                    "sort_order",
                )
                if invalid_response is not None:
                    return invalid_response
            changes = {
                "name": arguments.get("name"),
                "status": arguments.get("status"),
                "sort_order": sort_order,
            }
            try:
                result = TaskProjectRead.model_validate(
                    service.update_project(project_id, user=_user, **changes)
                ).model_dump()
            except ValueError as exc:
                return _jsonrpc_error(request_id, -32000, str(exc))
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "create_task_template":
            required_fields = [
                "project_id",
                "name",
                "default_estimated_duration_minutes",
                "default_reward_amount",
            ]
            missing = [field for field in required_fields if field not in arguments]
            if missing:
                return _invalid_params(
                    request_id,
                    f"Missing required argument: {missing[0]}",
                )
            project_id, invalid_response = _parse_int_argument(
                request_id,
                arguments["project_id"],
                "project_id",
            )
            if invalid_response is not None:
                return invalid_response
            duration_minutes, invalid_response = _parse_int_argument(
                request_id,
                arguments["default_estimated_duration_minutes"],
                "default_estimated_duration_minutes",
            )
            if invalid_response is not None:
                return invalid_response
            reward_amount, invalid_response = _parse_int_argument(
                request_id,
                arguments["default_reward_amount"],
                "default_reward_amount",
            )
            if invalid_response is not None:
                return invalid_response
            try:
                result = TaskTemplateRead.model_validate(
                    service.create_task_template(
                        project_id=project_id,
                        name=arguments["name"],
                        default_estimated_duration_minutes=duration_minutes,
                        default_reward_amount=reward_amount,
                        user=_user,
                        notes=arguments.get("notes", ""),
                        is_active=bool(arguments.get("is_active", True)),
                    )
                ).model_dump()
            except ValueError as exc:
                return _jsonrpc_error(request_id, -32000, str(exc))
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "update_task_template":
            if "template_id" not in arguments:
                return _invalid_params(request_id, "Missing required argument: template_id")
            template_id, invalid_response = _parse_int_argument(
                request_id,
                arguments["template_id"],
                "template_id",
            )
            if invalid_response is not None:
                return invalid_response
            duration_minutes = None
            if arguments.get("default_estimated_duration_minutes") is not None:
                duration_minutes, invalid_response = _parse_int_argument(
                    request_id,
                    arguments["default_estimated_duration_minutes"],
                    "default_estimated_duration_minutes",
                )
                if invalid_response is not None:
                    return invalid_response
            reward_amount = None
            if arguments.get("default_reward_amount") is not None:
                reward_amount, invalid_response = _parse_int_argument(
                    request_id,
                    arguments["default_reward_amount"],
                    "default_reward_amount",
                )
                if invalid_response is not None:
                    return invalid_response
            changes = {
                "name": arguments.get("name"),
                "default_estimated_duration_minutes": duration_minutes,
                "default_reward_amount": reward_amount,
                "notes": arguments.get("notes"),
                "is_active": arguments.get("is_active"),
            }
            try:
                result = TaskTemplateRead.model_validate(
                    service.update_task_template(template_id, user=_user, **changes)
                ).model_dump()
            except ValueError as exc:
                return _jsonrpc_error(request_id, -32000, str(exc))
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "create_daily_task":
            required_fields = [
                "task_template_id",
                "date",
                "estimated_duration_minutes",
                "reward_amount",
            ]
            missing = [field for field in required_fields if field not in arguments]
            if missing:
                return _invalid_params(
                    request_id,
                    f"Missing required argument: {missing[0]}",
                )
            task_template_id, invalid_response = _parse_int_argument(
                request_id,
                arguments["task_template_id"],
                "task_template_id",
            )
            if invalid_response is not None:
                return invalid_response
            target_date, invalid_response = _parse_date_argument(request_id, arguments["date"], "date")
            if invalid_response is not None:
                return invalid_response
            estimated_duration, invalid_response = _parse_int_argument(
                request_id,
                arguments["estimated_duration_minutes"],
                "estimated_duration_minutes",
            )
            if invalid_response is not None:
                return invalid_response
            reward_amount, invalid_response = _parse_int_argument(
                request_id,
                arguments["reward_amount"],
                "reward_amount",
            )
            if invalid_response is not None:
                return invalid_response
            try:
                result = DailyTaskRead.model_validate(
                    service.create_daily_task(
                        task_template_id=task_template_id,
                        date=target_date,
                        estimated_duration_minutes=estimated_duration,
                        reward_amount=reward_amount,
                        user=_user,
                    )
                ).model_dump()
            except ValueError as exc:
                return _jsonrpc_error(request_id, -32000, str(exc))
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "complete_daily_task":
            if "task_id" not in arguments:
                return _invalid_params(request_id, "Missing required argument: task_id")
            task_id, invalid_response = _parse_int_argument(
                request_id,
                arguments["task_id"],
                "task_id",
            )
            if invalid_response is not None:
                return invalid_response
            actual_duration = None
            if arguments.get("actual_duration_minutes") is not None:
                actual_duration, invalid_response = _parse_int_argument(
                    request_id,
                    arguments["actual_duration_minutes"],
                    "actual_duration_minutes",
                )
                if invalid_response is not None:
                    return invalid_response
            try:
                result = DailyTaskRead.model_validate(
                    service.complete_daily_task(
                        task_id,
                        user=_user,
                        actual_duration_minutes=actual_duration,
                    )
                ).model_dump()
            except ValueError as exc:
                return _jsonrpc_error(request_id, -32000, str(exc))
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "reopen_daily_task":
            if "task_id" not in arguments:
                return _invalid_params(request_id, "Missing required argument: task_id")
            task_id, invalid_response = _parse_int_argument(
                request_id,
                arguments["task_id"],
                "task_id",
            )
            if invalid_response is not None:
                return invalid_response
            try:
                result = DailyTaskRead.model_validate(
                    service.reopen_daily_task(task_id, user=_user)
                ).model_dump()
            except ValueError as exc:
                return _jsonrpc_error(request_id, -32000, str(exc))
            return _jsonrpc_result(request_id, _text_result(result))

        if tool_name == "spend_reward":
            required_fields = ["amount", "reason"]
            missing = [field for field in required_fields if field not in arguments]
            if missing:
                return _invalid_params(
                    request_id,
                    f"Missing required argument: {missing[0]}",
                )
            amount, invalid_response = _parse_int_argument(
                request_id,
                arguments["amount"],
                "amount",
            )
            if invalid_response is not None:
                return invalid_response
            try:
                result = RewardLedgerRead.model_validate(
                    service.spend_reward(amount, arguments["reason"], user=_user)
                ).model_dump()
            except ValueError as exc:
                return _jsonrpc_error(request_id, -32000, str(exc))
            return _jsonrpc_result(request_id, _text_result(result))

        return _jsonrpc_error(request_id, -32601, "Tool not found")

    if method == "ping":
        return _jsonrpc_result(request_id, {})

    raise HTTPException(status_code=404, detail="Method not found")
