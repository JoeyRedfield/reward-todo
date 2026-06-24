#!/usr/bin/env python3

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


COMMANDS = {
    "account-profile": {
        "description": "Get the current account profile.",
        "method": "GET",
        "path": "/account/profile",
        "params": [],
    },
    "projects-list": {
        "description": "List all task projects.",
        "method": "GET",
        "path": "/task-projects",
        "params": [],
    },
    "projects-add": {
        "description": "Create a task project.",
        "method": "POST",
        "path": "/task-projects",
        "params": [
            {"flag": "--name", "api_name": "name", "kind": "body", "required": True},
        ],
    },
    "projects-update": {
        "description": "Update a task project.",
        "method": "PATCH",
        "path": "/task-projects/{project_id}",
        "params": [
            {"flag": "--project-id", "api_name": "project_id", "kind": "path", "type": "int", "required": True},
            {"flag": "--name", "api_name": "name", "kind": "body"},
            {"flag": "--status", "api_name": "status", "kind": "body"},
            {"flag": "--sort-order", "api_name": "sort_order", "kind": "body", "type": "int"},
        ],
    },
    "templates-list": {
        "description": "List task templates, optionally filtered by project.",
        "method": "GET",
        "path": "/task-templates",
        "params": [
            {"flag": "--project-id", "api_name": "project_id", "kind": "query", "type": "int"},
        ],
    },
    "templates-add": {
        "description": "Create a task template.",
        "method": "POST",
        "path": "/task-templates",
        "params": [
            {"flag": "--project-id", "api_name": "project_id", "kind": "body", "type": "int", "required": True},
            {"flag": "--name", "api_name": "name", "kind": "body", "required": True},
            {
                "flag": "--duration",
                "api_name": "default_estimated_duration_minutes",
                "kind": "body",
                "type": "int",
                "required": True,
            },
            {
                "flag": "--reward",
                "api_name": "default_reward_amount",
                "kind": "body",
                "type": "int",
                "required": True,
            },
            {"flag": "--notes", "api_name": "notes", "kind": "body"},
            {"flag": "--inactive", "api_name": "is_active", "kind": "body", "type": "bool_flag"},
        ],
    },
    "templates-update": {
        "description": "Update a task template.",
        "method": "PATCH",
        "path": "/task-templates/{template_id}",
        "params": [
            {"flag": "--template-id", "api_name": "template_id", "kind": "path", "type": "int", "required": True},
            {"flag": "--name", "api_name": "name", "kind": "body"},
            {
                "flag": "--duration",
                "api_name": "default_estimated_duration_minutes",
                "kind": "body",
                "type": "int",
            },
            {
                "flag": "--reward",
                "api_name": "default_reward_amount",
                "kind": "body",
                "type": "int",
            },
            {"flag": "--notes", "api_name": "notes", "kind": "body"},
            {"flag": "--active", "api_name": "is_active", "kind": "body", "type": "true_flag"},
            {"flag": "--inactive", "api_name": "is_active", "kind": "body", "type": "bool_flag"},
        ],
    },
    "tasks-list": {
        "description": "List daily tasks for a specific date.",
        "method": "GET",
        "path": "/daily-tasks",
        "params": [
            {"flag": "--date", "api_name": "date", "kind": "query", "required": True},
        ],
    },
    "tasks-add": {
        "description": "Create a daily task from a template or as a standalone task.",
        "method": "POST",
        "path": "/daily-tasks",
        "params": [
            {"flag": "--date", "api_name": "date", "kind": "body", "required": True},
            {"flag": "--template-id", "api_name": "task_template_id", "kind": "body", "type": "int"},
            {"flag": "--name", "api_name": "name", "kind": "body"},
            {
                "flag": "--duration",
                "api_name": "estimated_duration_minutes",
                "kind": "body",
                "type": "int",
                "required": True,
            },
            {"flag": "--reward", "api_name": "reward_amount", "kind": "body", "type": "int", "required": True},
        ],
    },
    "tasks-delete": {
        "description": "Delete a standalone daily task.",
        "method": "DELETE",
        "path": "/daily-tasks/{task_id}",
        "params": [
            {"flag": "--task-id", "api_name": "task_id", "kind": "path", "type": "int", "required": True},
        ],
    },
    "tasks-complete": {
        "description": "Complete a daily task.",
        "method": "POST",
        "path": "/daily-tasks/{task_id}/complete",
        "params": [
            {"flag": "--task-id", "api_name": "task_id", "kind": "path", "type": "int", "required": True},
            {
                "flag": "--actual-duration",
                "api_name": "actual_duration_minutes",
                "kind": "body",
                "type": "int",
            },
        ],
    },
    "tasks-reopen": {
        "description": "Reopen a completed daily task.",
        "method": "POST",
        "path": "/daily-tasks/{task_id}/reopen",
        "params": [
            {"flag": "--task-id", "api_name": "task_id", "kind": "path", "type": "int", "required": True},
        ],
    },
    "rewards-summary": {
        "description": "Get the current reward summary.",
        "method": "GET",
        "path": "/rewards/summary",
        "params": [],
    },
    "rewards-ledger": {
        "description": "List recent reward ledger entries.",
        "method": "GET",
        "path": "/rewards/ledger",
        "params": [
            {"flag": "--limit", "api_name": "limit", "kind": "query", "type": "int"},
        ],
    },
    "rewards-spend": {
        "description": "Spend reward balance.",
        "method": "POST",
        "path": "/rewards/spend",
        "params": [
            {"flag": "--amount", "api_name": "amount", "kind": "body", "type": "int", "required": True},
            {"flag": "--reason", "api_name": "reason", "kind": "body", "required": True},
        ],
    },
}


def load_env_file():
    for candidate in (Path.home() / ".rewardtodo-tool.env", Path.cwd() / ".rewardtodo-tool.env"):
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def normalize_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/api"):
        return normalized
    parsed = urllib.parse.urlparse(normalized)
    if parsed.path in ("", "/"):
        path = "/api"
        return urllib.parse.urlunparse(parsed._replace(path=path))
    return normalized


def print_global_help():
    print("Reward Todo API Tools")
    print("")
    print("Usage:")
    print("  sh skills/reward-todo/scripts/rewardtools.sh list")
    print("  sh skills/reward-todo/scripts/rewardtools.sh help <command>")
    print("  sh skills/reward-todo/scripts/rewardtools.sh [--raw-response] <command> [command-options]")


def print_command_list():
    print("Supported commands:")
    for name in sorted(COMMANDS):
        print(f"  {name:16} {COMMANDS[name]['description']}")


def print_command_help(command_name: str):
    config = COMMANDS.get(command_name)
    if config is None:
        raise SystemExit(f"Unknown command: {command_name}")

    print(f"{command_name}")
    print(f"  {config['description']}")
    print(f"  {config['method']} {config['path']}")
    if not config["params"]:
        print("  No parameters.")
        return

    print("  Parameters:")
    for param in config["params"]:
        param_type = param.get("type", "string")
        requirement = "required" if param.get("required") else "optional"
        print(f"    {param['flag']:<18} {requirement}, {param_type}, {param['kind']}")


def parse_value(param, value):
    param_type = param.get("type", "string")
    if param_type == "int":
        try:
            return int(value)
        except ValueError as exc:
            raise SystemExit(f"Invalid integer for {param['flag']}: {value}") from exc
    return value


def parse_command_args(config, argv):
    path_values = {}
    query_values = {}
    body_values = {}

    params_by_flag = {param["flag"]: param for param in config["params"]}
    index = 0
    while index < len(argv):
        token = argv[index]
        if token not in params_by_flag:
            raise SystemExit(f"Unknown option: {token}")

        param = params_by_flag[token]
        if param.get("type") == "bool_flag":
            value = False
        elif param.get("type") == "true_flag":
            value = True
        else:
            index += 1
            if index >= len(argv):
                raise SystemExit(f"Missing value for {token}")
            value = parse_value(param, argv[index])

        if param["kind"] == "path":
            path_values[param["api_name"]] = value
        elif param["kind"] == "query":
            query_values[param["api_name"]] = value
        else:
            body_values[param["api_name"]] = value
        index += 1

    for param in config["params"]:
        if param.get("required"):
            target = {
                "path": path_values,
                "query": query_values,
                "body": body_values,
            }[param["kind"]]
            if param["api_name"] not in target:
                raise SystemExit(f"Missing required option: {param['flag']}")

    if config["path"] == "/daily-tasks" and config["method"] == "POST":
        has_template = body_values.get("task_template_id") is not None
        name_value = body_values.get("name")
        has_name = isinstance(name_value, str) and name_value.strip() != ""
        if has_template == has_name:
            raise SystemExit("tasks-add requires either --template-id or --name")

    if "is_active" not in body_values and any(param["api_name"] == "is_active" for param in config["params"]):
        body_values["is_active"] = True

    return path_values, query_values, body_values


def make_request(base_url: str, token: str, config, path_values, query_values, body_values):
    path = config["path"].format(**path_values)
    url = f"{base_url}{path}"
    if query_values:
        url = f"{url}?{urllib.parse.urlencode(query_values)}"

    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    if config["method"] != "GET":
        data = json.dumps(body_values).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, method=config["method"], headers=headers, data=data)

    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        message = body
        try:
            payload = json.loads(body)
            message = payload.get("detail", body)
        except json.JSONDecodeError:
            pass
        raise SystemExit(f"HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Request failed: {exc.reason}") from exc


def main():
    load_env_file()
    argv = sys.argv[1:]
    raw_response = False

    while argv and argv[0].startswith("--"):
        option = argv.pop(0)
        if option == "--raw-response":
            raw_response = True
            continue
        raise SystemExit(f"Unknown global option: {option}")

    if not argv:
        print_global_help()
        raise SystemExit(1)

    command = argv.pop(0)
    if command == "list":
        print_command_list()
        return
    if command == "help":
        if not argv:
            raise SystemExit("Usage: help <command>")
        print_command_help(argv[0])
        return

    config = COMMANDS.get(command)
    if config is None:
        raise SystemExit(f"Unknown command: {command}")

    base_url = os.environ.get("REWARDTOOL_SERVER_BASEURL")
    token = os.environ.get("REWARDTOOL_TOKEN")
    if not base_url or not token:
        raise SystemExit(
            "REWARDTOOL_SERVER_BASEURL and REWARDTOOL_TOKEN are required. "
            "You can export them in your shell or put them in ~/.rewardtodo-tool.env"
        )

    normalized_base_url = normalize_base_url(base_url)
    path_values, query_values, body_values = parse_command_args(config, argv)
    result = make_request(normalized_base_url, token, config, path_values, query_values, body_values)

    if raw_response:
        print(json.dumps(result, ensure_ascii=False))
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
