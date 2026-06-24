import importlib.util
from pathlib import Path

import pytest


def _load_rewardtools_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "reward-todo"
        / "scripts"
        / "rewardtools.py"
    )
    spec = importlib.util.spec_from_file_location("rewardtools_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_tasks_add_mode_accepts_template_and_standalone_modes() -> None:
    rewardtools = _load_rewardtools_module()

    rewardtools.validate_tasks_add_mode({"task_template_id": 1})
    rewardtools.validate_tasks_add_mode({"name": "独立任务"})


def test_tasks_delete_command_is_exposed_and_parses_task_id() -> None:
    rewardtools = _load_rewardtools_module()

    assert "tasks-delete" in rewardtools.COMMANDS

    command = rewardtools.COMMANDS["tasks-delete"]
    path_values, query_values, body_values = rewardtools.parse_command_args(
        command,
        ["--task-id", "42"],
    )

    assert path_values == {"task_id": 42}
    assert query_values == {}
    assert body_values == {}


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "tasks-add requires one of: --template-id or --name"),
        (
            {"task_template_id": 1, "name": "独立任务"},
            "tasks-add does not allow --template-id and --name together",
        ),
    ],
)
def test_validate_tasks_add_mode_rejects_invalid_mode_combinations(payload, message) -> None:
    rewardtools = _load_rewardtools_module()

    with pytest.raises(SystemExit, match=message):
        rewardtools.validate_tasks_add_mode(payload)
