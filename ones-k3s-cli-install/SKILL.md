---
name: ones-k3s-cli-install
description: Install ONES single-node (K3S) in TTY mode using the official flow and token-efficient logging. Use when performing fresh install/reinstall, uninstall-before-install, CLI method (3.3 method 2), interactive init-config defaults, rollout checks, and final access verification on port 30011.
---

# ONES K3S CLI Install (Token-Efficient + TTY)

Follow `https://opsdoc.ones.cn/docs/install-upgrade/K3S/install-new`.

## Goals

- This skill is `TASK_TYPE=install` only; do not run upgrade flow commands from `upgrade-info` here.
- Use **TTY execution** for interactive steps.
- If `kubectl` exists, **uninstall first** and clean `/data/ones`.
- Install using offline package via `quickstart.sh`.
- Use **method 3.3-2 (command line)**:
  - `ones-ai-k8s.sh make init-config`
  - `ones-ai-k8s.sh bash script/ones/deploy-ones.sh`
- Keep chat output compact; keep full logs remote.

## Inputs

Do not hardcode host/IP/login or version.

Required runtime inputs:

- `HOST` (SSH target)
- `ONES_VERSION` (example: `v6.18.47`)
- Init defaults:
  - `defaultLanguage` (default `zh`)
  - `timezone` (default `Asia/Shanghai`)
  - `teamName` (default `ONES`)
  - `ownerName` (default `admin`)
  - `ownerEmail` (default `admin@localhost.ai`)
  - `ownerPassword` (default `0nesAdmin2026!`)

## Step 1: Pre-check + uninstall (if needed)

Run on target:

1. Check `kubectl`.
2. If present, **must ask for human confirmation before uninstall** (do not execute uninstall directly without explicit user approval in current chat).
3. After approval, run uninstall with required confirmation text:
   - `/usr/bin/all-uninstall.sh` (or `/data/ones/ones-installer-pkg/all-uninstall.sh`)
   - confirmation: `delete-ones-data`
4. Force cleanup:
   - `rm -rf /data/ones && mkdir -p /data/ones`
   - Ensure `:6443` is free before reinstall.

## Step 2: Download + deploy installer (TTY)

In `/data/pkg`:

1. Ensure `quickstart.sh` exists.
2. Download offline package:
   - `bash quickstart.sh --version ${ONES_VERSION} --download`
3. Deploy installer:
   - `bash quickstart.sh --offline-file <resolved_offline_pkg_path>`

Important:

- Run in **TTY** (`ssh -tt`) to avoid interactive hang.
- If envcheck prompts yes/no for warnings, choose default continue (`yes`) unless user asks to stop.

## Step 3: Method 3.3-2 CLI install

From `/data/ones/ones-installer-pkg`:

1. `./ones-ai-k8s.sh make init-config`
2. Feed interactive values:
   - Terms confirm: `yes`
   - `defaultLanguage`: configured value
   - `timezone`: can input timezone index or value (`Asia/Shanghai`)
   - `teamName`, `ownerName`, `ownerEmail`, `ownerPassword`
   - Final save confirm: `yes`
3. Deploy:
   - `./ones-ai-k8s.sh bash script/ones/deploy-ones.sh`

## Step 4: Verification

Check all of the following:

1. `kubectl get nodes` is `Ready`.
2. Key namespaces exist: `ones`, `ones-op`, `ones-installer`.
3. Key workloads available (project-api/wiki-api/platform/open-api).
4. Service `access-nodeport` exposes `30011`.
5. HTTP check:
   - `curl -I http://<node-ip>:30011`
   - `200/302` is acceptable for availability.

## Execution guardrails (install/upgrade isolation)

- Before each step, print: `phase`, `doc_command`, `actual_command`.
- If `actual_command` is an upgrade-only command, fail-fast and stop.
- Keep install artifacts/logs isolated:
  - install path/log prefix only (`/data/pkg` + `/tmp/ones-install-*.log`).
  - do not write install logs under `/tmp/ones-upgrade-*.log`.

## Token-efficient output policy

Never paste full installer logs by default.

Return compact status blocks only:

- Current phase (`uninstall`, `deploy installer`, `init-config`, `deploy-ones`, `verify`)
- Blocking error (if any) + one-line reason
- Next action
- Remote log path(s)

For periodic updates, use:

- `当前步骤 / 是否报错 / 下一步`

## Common failure handling

- `envcheck rc=137` / hangs near envcheck:
  - Ensure old tasks are stopped.
  - Ensure `6443` free (no residual k3s).
  - Re-run in **TTY**.
- Port conflict (e.g. `6443`):
  - stop residual k3s/installer processes, uninstall again if needed.
- MySQL rollout timeout during deploy:
  - continue monitoring rollout retries; report concise progress.

## Completion report template

- Host: `<HOST>`
- Version: `<ONES_VERSION>`
- Uninstall performed: yes/no
- Install method: 3.3 method 2 (CLI)
- Access account (ownerEmail): `<ownerEmail>`
- Access password (ownerPassword): `<ownerPassword>`
- Init values applied: language/timezone/team/ownerEmail/ownerPassword
- Verification:
  - node ready: yes/no
  - core namespaces/workloads: yes/no
  - `http://<ip>:30011`: reachable yes/no (HTTP code)
- Warnings (if any)
- Final result: success/fail
