---
name: ones-k3s-upgrade-cli
description: Upgrade ONES single-node K3S environments by strictly following the official upgrade documentation flow (prep, backup, package import, migration, post-upgrade 2.6/2.7/2.8/2.9), with token-efficient logging and mandatory manual confirmation on exceptions. Use when a user asks to upgrade ONES on a server and provides per-run connection method and target version.
---

# ONES K3S Upgrade CLI (Strict-Doc + Token-Efficient)

Follow `https://opsdoc.ones.cn/docs/install-upgrade/upgrade/upgrade-info` strictly.

## Required runtime inputs (must be provided each run)

Do not hardcode from previous runs.

- `LOGIN_METHOD` (for example: `ssh root@<host>` or equivalent provided by user)
- `TARGET_VERSION` (for example: `v6.100.5`)

Optional but recommended:

- `SRC_VERSION` (if not provided, detect from environment)
- `ONES_DATA_DIR` (auto-detect from installer-api Path if omitted)

## Hard rules

1. **Task-type isolation (mandatory)**: this skill is `TASK_TYPE=upgrade`; never execute install-skill flows/commands as substitutes.
2. **Strict order**: execute in document order; do not skip 2.1/2.2 backups.
3. **Default auto-continue**: if a step succeeds, continue to next step immediately without waiting for extra confirmation.
4. **Exception handling**: if a step errors, stop current operation immediately, report error summary + log path, and wait for explicit user confirmation before continuing.
5. **Auto-confirm cutover on nearing-completion signal**: when migration logs contain `migration is nearing completion and manual confirmation can be done anytime now.`, execute `make confirm-migration MIGRATION_DIR=config/migration` immediately (no extra user confirmation).
6. **Non-interactive first**: run commands in non-interactive shells (`kubectl exec` without `-it`); for interactive prompts, auto-feed confirmation (for example `printf "yes\n" | ...`) or use `SKIP_DIFF=true` when the workflow supports it.
7. **Command-gate before every step**: print `phase/doc_command/actual_command`; if `actual_command` is not the documented command (or a documented equivalent), fail-fast and stop.
8. **Path/log isolation**: use only upgrade paths and logs (`/data/upgrade/...`, `/tmp/ones-upgrade-*.log`).
9. **Progress report every 5 minutes**: proactively report current phase / error status / next action / key log path.
10. **Token-efficient output**: keep full logs on remote, return compact status only.

## Workflow

### Phase 0: Precheck

- Verify cluster reachability and installer path.
- Detect current version from `config/public.yaml` (`onesVersion`).
- Detect data dir from:
  - `kubectl -n ones-installer describe deploy installer-api | grep Path:`

Report:
- host, src version, target version, detected data dir.

### Phase 1: Upgrade preparation (doc 1.1~1.4)

- Check prerequisites per doc.
- Prepare `/data/upgrade`.
- Download/build offline package using `SRC_VERSION -> TARGET_VERSION`.
- If offline package build fails near completion with transient network errors (for example `read: connection timed out`), rerun the same build command once before escalating.
- For doc 1.3 image registry port conflicts, explicitly set `IMAGE_REGISTRY_PORT=5001` when required by doc/environment.
- Avoid `--help` probing on build script if it triggers environment checks; run the documented build command directly.
- Confirm package artifact path exists.

### Phase 2: **Mandatory backups** (doc 2.1 / 2.2)

Do not continue until both steps complete.

- 2.1 backup config:
  - Prefer direct non-interactive execution in installer pod (`kubectl exec ... -- bash -lc "cd /data/ones/ones-ai-k8s && make backup-config"`), do not rely
 on `ones-ai-k8s.sh` interactive TTY path.
  - fallback to manual config copy if command incompatible.
- 2.2 backup business data:
  - Prefer direct non-interactive execution in installer pod.
  - `make mysql-base-backup NAMESPACE=ones`
  - `make logs-mysql-xbackup NAMESPACE=ones` (capture result)

If backup command fails:
- stop immediately,
- report error summary + log path,
- wait for user decision before continuing.

### Phase 3: Upgrade execution (doc 2.3~2.5)

- 2.3 import offline package with the documented command shape:
  - `OFFLINE_PKG=<offline_pkg_tar_name> ONES_DATA_DIR=<ones_data_dir> bash install_linux_amd64.sh`
  - Example only: `OFFLINE_PKG=offline_pkg_v6.100.5.tar ONES_DATA_DIR=/data/ones bash install_linux_amd64.sh`
  - Do not replace this with install-skill quickstart install flow.
- Update installer and initialize:
  - `make setup-installer-api`
  - **Important session handoff after installer update**:
    - After `make setup-installer-api`, **exit current installer-api pod/session immediately**, then wait `sleep 60` before running next make targets.
    - Reason: installer-api pod may be recreated during this step; continuing in the old session can cause next step (especially `make setup-ones-cluster-operator`) to exit with code `137`.
    - Suggested pattern:
      - run `make setup-installer-api`
      - `exit` current pod shell
      - `sleep 60`
      - re-enter latest installer-api pod and continue.
  - `make setup-ones-cluster-operator`
  - `make setup-tidb-operator`
  - `make init-config`
  - `make init-db`
- 2.5 start migration:
  - `make start-migration MIGRATION_DIR=config/migration`
  - track migration progress.

When log shows `migration is nearing completion and manual confirmation can be done anytime now.`:
- execute `make confirm-migration MIGRATION_DIR=config/migration` immediately,
- for non-interactive shells, pipe confirmation input (for example `printf "yes\n" | make confirm-migration MIGRATION_DIR=config/migration`).

### Phase 4: Post-upgrade required operations (doc 2.6~2.9)

#### 2.6
- `make setup-ones-inner-plugins`

#### 2.7
- `make setup-ones-built-in-redis`
- `make setup-ones-built-in-kafka`
- `make setup-ones-built-in-tikv`
- For non-interactive execution, if diff prompt blocks progress, rerun with `SKIP_DIFF=true`.
- restart related workloads:
  - `kubectl get pod -n ones | grep -iE 'api|wiz|platform|plugin' | awk '{print $1}' | xargs -r kubectl delete pod -n ones`
- `make rebuild-cdc`
- check abnormal pods:
  - `kubectl get pod -A | grep -vE 'Running|Completed'`

#### 2.8 rebuild performance
- run `reset_performance_k3s.sh -a`
- if script missing, download first: `curl -fL -O https://res.ones.pro/script/reset_performance_k3s.sh && chmod +x reset_performance_k3s.sh`
- poll `reset_performance_k3s.sh -s` until both pipelines are dump-finished / incremental syncing (or equivalent completed state)

#### 2.9 rebuild kilob index
- edit `config/private.yaml` with values different from last run:
  - `kilobSyncSchemaHash: "<1~2 digit value>"`
  - `kilobForceSnapshotVersion: "<1~2 digit value>"`
  - `kilobForceSnapshotAll: "true"`
- Note: hash/version only need to be one-digit or two-digit numbers; must differ from previous value.
- apply:
  - `make setup-ones` (if diff prompt blocks non-interactive run, use `make setup-ones SKIP_DIFF=true`)
- validate progress / completion:
  - `kubectl logs -n ones -l app=kilob-sync --tail=200`
  - `make print-kilob-index` (if supported)

### Phase 5: Final verification

Minimum checks:
- `onesVersion` equals target version.
- migration job completed.
- core deployments healthy.
- `access-nodeport` exists (`30011`).
- `curl -I http://<node-ip>:30011` returns reachable status.

## 5-minute progress report format

Use this compact format every 5 minutes:

- 当前步骤: `<phase>`
- 是否报错: `否/是（简述）`
- 下一步: `<next action>`
- 关键日志: `<remote log path>`

## Token-efficient logging policy

- Keep full output in remote log files under `/tmp/ones-upgrade-*.log`.
- Never paste long raw logs by default.
- Return only summary, key evidence lines, and log paths.
- For each executed step, record a compact audit line: `time | phase | doc_section | actual_command | result | log_path`.

## Completion report template

- Host/Login: `<LOGIN_METHOD>`
- Source Version: `<SRC_VERSION>`
- Target Version: `<TARGET_VERSION>`
- Backups:
  - 2.1 backup-config: success/fail (path/evidence)
  - 2.2 mysql-base-backup: success/fail (path/evidence)
- Migration:
  - start-migration: success/fail
  - confirm-migration: auto-triggered on nearing-completion signal; result
- Post-upgrade:
  - 2.6: done/not done
  - 2.7: done/not done
  - 2.8: done/not done + sync status
  - 2.9: done/not done + kilob hash/version used
- Verification:
  - NodePort 30011: yes/no
  - HTTP check: code
  - Core workloads: healthy yes/no
- Exceptions and manual confirmations
- Final result: success/fail
