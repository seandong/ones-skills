---
name: jumpserver-devops
description: Execute common dev-environment operations through JumpServer API, including listing authorized hosts, listing host system users, running remote shell commands with log polling, obtaining SSH connection parameters, and opening SSH sessions via temporary credentials. Use this skill when the task mentions JumpServer/dev host operations, SSH login, host inventory lookup, or batch/one-off command execution on managed servers.
---

# JumpServer DevOps

Use this skill to operate dev hosts in JumpServer with API signatures based on `AccessKey/SecretKey`.

## Quick Workflow

1. Load credentials from `~/.onesdev.env` (preferred) or environment variables.
2. Discover target host with `list-hosts`.
3. Discover allowed system user with `list-system-users --asset-id`.
4. Choose one operation:
- Execute command and read logs: `run-command`
- Fetch SSH parameters only: `ssh-params`
- Open SSH session directly: `ssh-connect`

## Credentials

Use these variables:

- `JMS_BASE_URL` (default: `https://devjumpserver.myones.net`)
- `JMS_ACCESS_KEY`
- `JMS_SECRET_KEY`

Preferred file: `~/.onesdev.env`

```env
JMS_BASE_URL=https://devjumpserver.myones.net
JMS_ACCESS_KEY=your-access-key
JMS_SECRET_KEY=your-secret-key
```

If missing, stop and prompt user to create/fix `~/.onesdev.env`.

## Commands

Run script:

```bash
python scripts/jms_ops.py <subcommand> [args]
```

### list-hosts

```bash
python scripts/jms_ops.py list-hosts --search k3s --limit 20 --json
```

### list-system-users

```bash
python scripts/jms_ops.py list-system-users --asset-id <asset_id> --json
```

### run-command

```bash
python scripts/jms_ops.py run-command \
  --asset-id <asset_id> \
  --system-user-id <system_user_id> \
  --command 'uname -a' \
  --timeout 120
```

### ssh-params

Default masks password.

```bash
python scripts/jms_ops.py ssh-params \
  --asset-id <asset_id> \
  --system-user-id <system_user_id> \
  --json
```

Show raw password only when explicitly needed:

```bash
python scripts/jms_ops.py ssh-params \
  --asset-id <asset_id> \
  --system-user-id <system_user_id> \
  --raw --json
```

### ssh-connect

```bash
python scripts/jms_ops.py ssh-connect \
  --asset-id <asset_id> \
  --system-user-id <system_user_id>
```

Use `--print-only` to avoid opening an interactive session.

## Safety Rules

- Do not hardcode keys in files.
- Do not print `JMS_SECRET_KEY`.
- Mask SSH passwords by default unless user asks for raw.
- Report API errors with endpoint and HTTP status.

## Resources

- Script: `scripts/jms_ops.py`
- API notes: `references/api.md`
