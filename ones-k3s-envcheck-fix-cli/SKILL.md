---
name: ones-k3s-envcheck-fix-cli
description: Run K3S envcheck and apply linux-fix remediations for ONES servers, then rerun checks and output a structured final report with pass/fail items.
---

# ONES K3S Envcheck + Linux Fix CLI

Follow these docs strictly:
- `https://opsdoc.ones.cn/docs/environmental-requirements/K3S/envcheck`
- `https://opsdoc.ones.cn/docs/environmental-requirements/K3S/linux-fix`

## Required runtime inputs

- `LOGIN_METHOD` (example: `ssh root@<host>`)
- `CHECK_PROFILE` (`case1`/`case2`/`case3`/`case4`)

Profile mapping:
- `case1`: `--cpu-cores 8 --data-disk-size 250GB --mem-size 24GB`
- `case2`: `--cpu-cores 16 --data-disk-size 1000GB --mem-size 48GB`
- `case3`: `--cpu-cores 32 --data-disk-size 2000GB --mem-size 64GB`
- `case4`: `--cpu-cores 48 --data-disk-size 4000GB --mem-size 96GB`

## Hard rules

1. Execute as `root`.
2. Keep full logs on remote under `/tmp/envcheck-<ts>/` and `/tmp/linux-fix-<ts>.log`.
3. Non-interactive first.
4. Do not kill business processes (port conflicts) unless user explicitly approves.
5. After fix actions, always rerun envcheck and report delta.

## Workflow

### Phase 0: Precheck

- Check host time, arch, connectivity.
- Ensure dirs:
- `/data/ones`
- `/data/ones/ones-local-storage/tidb`

### Phase 1: Envcheck run

1. Download envcheck package by latest version:
- amd64: `.../linux/amd64/envcheck.tar`
- arm64: `.../linux/arm64/envcheck.tar`
2. Extract and run selected profile.
3. Save logs to `/tmp/envcheck-<ts>/<profile>.log`.

### Phase 2: Linux fix actions

Apply safe automatic fixes from linux-fix:

- DNS resolver:
- replace symlink `/etc/resolv.conf` with static file (valid nameservers)
- hosts mapping: add `<host-ip> <hostname>`

- Swap:
- `swapoff -a`
- comment swap entries in `/etc/fstab`

- Firewall:
- `systemctl stop/disable ufw || firewalld`
- `iptables -F`

- sysctl:
- write `/etc/sysctl.d/99-ones-envcheck.conf`
- `sysctl --system`

- file limits:
- append to `/etc/security/limits.conf`:
- `root soft nofile 1000000`
- `root hard nofile 1000000`
- `* soft nofile 1000000`
- `* hard nofile 1000000`

- graphical target:
- `systemctl set-default multi-user.target`

- time sync:
- install and configure `chrony`
- enable service and `timedatectl set-ntp true`

### Phase 3: Rerun envcheck

- Rerun with same `CHECK_PROFILE`.
- Compare before/after pass/fail.
- Extract remaining blockers.

## Common remaining blockers (manual)

- Memory below profile requirement.
- Port conflict (`80/443` often used by nginx).
- Data disk not separated from system disk (`Warning`).

## Output report format

- Host/Login: `<LOGIN_METHOD>`
- Profile: `<CHECK_PROFILE>`
- Initial result:
- passed items: `<count/list>`
- failed items: `<list>`
- warning items: `<list>`
- Applied fixes:
- DNS/hosts: done/not done
- swap/fstab: done/not done
- firewall/iptables: done/not done
- sysctl: done/not done
- limits: done/not done
- GUI target: done/not done
- chrony/time sync: done/not done
- Rerun result:
- newly passed: `<list>`
- still failed: `<list>`
- still warning: `<list>`
- Evidence:
- envcheck log: `</tmp/envcheck-.../...log>`
- linux-fix log: `</tmp/linux-fix-...log>`
- Final conclusion:
- `PASS` if no failed items
- `BLOCKED` with blockers if failed items remain

## Command skeleton

```bash
# 1) envcheck
ssh root@<host> '... download envcheck ...; ./envcheck <profile-args> > /tmp/envcheck-<ts>/<profile>.log 2>&1'

# 2) linux-fix
ssh root@<host> '... apply dns/swap/firewall/sysctl/limits/chrony ... > /tmp/linux-fix-<ts>.log 2>&1'

# 3) rerun
ssh root@<host> './envcheck <profile-args> > /tmp/envcheck-<ts>/<profile>-after-fix.log 2>&1'
```
