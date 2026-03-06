---
name: ones-k3s-start-stop-cli
description: Safely stop and start ONES single-node K3S services by following start-stop.md, including precheck, ordered scale operations, manual-confirm resume, and readiness verification.
---

# ONES K3S Start/Stop CLI (Single Node)

Follow `https://opsdoc.ones.cn/docs/matching/K3S/start-stop` strictly.

## Required runtime inputs

- `LOGIN_METHOD` (example: `ssh root@<host>`)

Optional:
- `REQUIRE_MANUAL_CONFIRM_BEFORE_START` (default: `true`)

## Hard rules

1. This skill is only for **single-node ONES K3S**.
2. Stop order must be: business -> mysql -> etcd (if exists).
3. Start order must be: mysql -> business -> etcd (if exists).
4. After stop is done, if `REQUIRE_MANUAL_CONFIRM_BEFORE_START=true`, wait for explicit user confirmation before start.
5. Use non-interactive commands and keep logs under `/tmp/ones-stop-*.log` and `/tmp/ones-start-*.log`.
6. Do not reboot/poweroff unless user explicitly asks.

## Stop workflow

### Phase 0: Precheck

- Record baseline replicas/pods:
- `kubectl get pod -A | grep -iE 'wiz-editor-server-statefulset|project-api-deployment|wiki-api-deployment'`
- `kubectl -n ones get deploy project-api-deployment wiki-api-deployment`
- `kubectl -n ones get sts wiz-editor-server-statefulset mysql-operator mysql-cluster-mysql`
- `kubectl -n ones get mysqlcluster mysql-cluster`

### Phase 1: Stop key business

- `kubectl -n ones scale --replicas=0 deploy project-api-deployment wiki-api-deployment`
- `kubectl -n ones scale --replicas=0 sts wiz-editor-server-statefulset`

### Phase 2: Stop MySQL (skip if external DB)

- `kubectl -n ones scale --replicas=0 mysqlcluster mysql-cluster`
- `kubectl -n ones scale --replicas=0 sts mysql-operator`
- `kubectl -n ones scale --replicas=0 sts mysql-cluster-mysql`

### Phase 3: Stop etcd in ones-op (if exists)

- `kubectl -n ones-op scale --replicas=0 sts etcd`

### Phase 4: Stop verification

- Verify scales:
- `kubectl -n ones get deploy project-api-deployment wiki-api-deployment -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,READY:.status.readyReplicas`
- `kubectl -n ones get sts wiz-editor-server-statefulset mysql-operator mysql-cluster-mysql -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,READY:.status.readyReplicas`
- `kubectl -n ones-op get sts etcd -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,READY:.status.readyReplicas`

Note:
- Pods may remain in `Terminating` briefly.
- `ones-project-api-deployment` is not part of this doc's stop list; do not scale it unless user requests.

## Start workflow

### Phase 0: Precheck node readiness

- Wait until `kubectl get nodes` shows `Ready`.

### Phase 1: Start MySQL (skip if external DB)

- `kubectl -n ones scale --replicas=1 mysqlcluster mysql-cluster`
- `kubectl -n ones scale --replicas=1 sts mysql-operator`

### Phase 2: Start business

- `kubectl -n ones scale --replicas=1 deploy project-api-deployment wiki-api-deployment`
- `kubectl -n ones scale --replicas=1 sts wiz-editor-server-statefulset`

### Phase 3: Start etcd in ones-op (if exists)

- `kubectl -n ones-op scale --replicas=1 sts etcd`

### Phase 4: Start verification

- Scale check:
- `kubectl -n ones get deploy project-api-deployment wiki-api-deployment -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,READY:.status.readyReplicas`
- `kubectl -n ones get sts wiz-editor-server-statefulset mysql-operator mysql-cluster-mysql -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,READY:.status.readyReplicas`

- Non-running pods check (important: avoid header false-positive):
- `kubectl get pod -n ones --no-headers | grep -v Running | grep -v Complete`
- If no output, ONES pods are healthy for this check.

## Common pitfalls

1. `Terminating` lasts several minutes for mysql/wiz pods during stop/start transitions.
2. `kubectl get pod ...` with header can cause false loop conditions; use `--no-headers` in script checks.
3. If node reboot is requested between stop and start, recheck node `Ready` before scaling up.

## Completion report template

- Host/Login: `<LOGIN_METHOD>`
- Stop result:
- business scale: done/not done
- mysql scale: done/not done
- etcd scale: done/not done
- Start result:
- mysql scale: done/not done
- business scale: done/not done
- etcd scale: done/not done
- Final health:
- node ready: yes/no
- non-running pods in ones: count/list
- Exceptions and manual confirmations
- Final result: success/fail
