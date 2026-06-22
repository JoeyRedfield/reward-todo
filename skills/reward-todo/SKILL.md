---
name: reward-todo
description: Use Reward Todo API Tools to query projects, templates, daily tasks and rewards, or create and complete tasks through the Reward Todo HTTP API.
---

# Reward Todo API Tools

## Usage

### List all supported commands

Linux / macOS

```bash
sh skills/reward-todo/scripts/rewardtools.sh list
```

### Show help for a specific command

Linux / macOS

```bash
sh skills/reward-todo/scripts/rewardtools.sh help <command>
```

### Call API

Linux / macOS

```bash
sh skills/reward-todo/scripts/rewardtools.sh [global-options] <command> [command-options]
```

## Supported Commands

- `account-profile`
- `projects-list`
- `projects-add`
- `projects-update`
- `templates-list`
- `templates-add`
- `templates-update`
- `tasks-list`
- `tasks-add`
- `tasks-complete`
- `tasks-reopen`
- `rewards-summary`
- `rewards-ledger`
- `rewards-spend`

## Troubleshooting

If the script reports that `REWARDTOOL_SERVER_BASEURL` or `REWARDTOOL_TOKEN` is not set, define them in your shell environment, or create `~/.rewardtodo-tool.env`.

The meanings of these environment variables are as follows:

| Variable | Required | Description |
| --- | --- | --- |
| `REWARDTOOL_SERVER_BASEURL` | Required | Reward Todo API base URL, usually the `api_base_url` returned when you create an API token, e.g. `http://localhost:8088/api` |
| `REWARDTOOL_TOKEN` | Required | Reward Todo API token |

Example:

```bash
export REWARDTOOL_SERVER_BASEURL="http://localhost:8088/api"
export REWARDTOOL_TOKEN="<api-token>"
sh skills/reward-todo/scripts/rewardtools.sh projects-list
```
