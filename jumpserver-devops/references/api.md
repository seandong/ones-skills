# JumpServer API Reference (DevOps Skill)

Base URL example:

- `https://devjumpserver.myones.net`

Auth:

- HMAC signature header format: `Authorization: Signature ...`
- Signed headers: `(request-target) accept date`

## Host Inventory

- `GET /api/v1/perms/users/assets/`
- Purpose: list assets accessible by current JumpServer user.
- Typical query params: `search`, `limit`, `offset`

## Host System Users

- `GET /api/v1/perms/users/assets/{asset_id}/system-users/`
- Purpose: list system users allowed on a target host.

## Command Execution

- `POST /api/v1/ops/command-executions/`
- Body:

```json
{
  "command": "echo hello",
  "run_as": "<system_user_id>",
  "hosts": ["<asset_id>"]
}
```

Response contains `log_url`, for example:

- `/api/v1/ops/celery/task/{task_id}/log/`

Poll log with optional `mark` query for incremental reads:

- `GET /api/v1/ops/celery/task/{task_id}/log/?mark=<mark>`

## SSH Temporary Connection

- `POST /api/v1/users/connection-token/client-url/`
- Body:

```json
{
  "asset": "<asset_id>",
  "system_user": "<system_user_id>"
}
```

Response includes `url` in `jms://<base64-json>` format.

Decoded payload includes nested token JSON with temporary SSH fields:

- `ip`
- `port`
- `username`
- `password`

Use these fields for `ssh-params` and `ssh-connect` commands.
