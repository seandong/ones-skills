---
name: ones-k3s-open-multi-team-cli
description: Enable ONES multi-team mode on single-node K3S by following open-multi-team.md, execute the irreversible SQL update safely, and verify visibility state.
---

# ONES K3S Open Multi-Team CLI

Follow `https://opsdoc.ones.cn/docs/matching/K3S/open-multi-team` strictly.

## Required runtime inputs

- `LOGIN_METHOD` (example: `ssh root@<host>`)

## Hard rules

1. This operation is **irreversible**. Explicitly remind user before executing SQL.
2. For external DB scenarios, do not run SQL in cluster; provide SQL to customer DBA.
3. Use non-interactive execution (`kubectl exec ... --`).
4. Verify result from database after execution; do not rely only on command exit code.

## Workflow

### Phase 0: Preconditions

- Ensure ONES is running and mysql pod is healthy (internal DB case):
- `kubectl -n ones get pod mysql-cluster-mysql-0`
- Locate installer pod:
- `POD=$(kubectl -n ones-installer get pods | awk '/installer-api/{print $1; exit}')`

### Phase 1: Collect DB connection values

Run in installer pod (`/data/ones/ones-ai-k8s`):

- `PW=$(make get_value KEY=mysqlPassword)`
- `USER=$(make get_value KEY=mysqlUser)`
- `HOST=$(make get_value KEY=mysqlHost)`
- `PORT=$(make get_value KEY=mysqlPort)`

### Phase 2: Enable multi-team

Execute SQL in mysql pod:

- `update project.organization set visibility = 1;`

Reference command:

```bash
kubectl -n ones exec mysql-cluster-mysql-0 -- \
  mysql -u$USER -p$PW -h$HOST -P$PORT \
  -e 'update project.organization set visibility = 1;'
```

### Phase 3: Verification

Database-side verification:

```bash
kubectl -n ones exec mysql-cluster-mysql-0 -- \
  mysql -u$USER -p$PW -h$HOST -P$PORT -N -e \
  'select count(*) as total, sum(case when visibility=1 then 1 else 0 end) as enabled from project.organization;'
```

Optional detail check:

```bash
kubectl -n ones exec mysql-cluster-mysql-0 -- \
  mysql -u$USER -p$PW -h$HOST -P$PORT -e \
  'show columns from project.organization;'

kubectl -n ones exec mysql-cluster-mysql-0 -- \
  mysql -u$USER -p$PW -h$HOST -P$PORT -e \
  'select uuid,name,visibility from project.organization;'
```

UI verification (manual):
- Login ONES, open `配置中心`; if `组织配置` appears, multi-team is enabled.

## External DB note

If DB is external, provide SQL to customer DBA:

```sql
update project.organization set visibility = 1;
```

## Completion report template

- Host/Login: `<LOGIN_METHOD>`
- DB mode: internal/external
- SQL executed: yes/no
- DB verification:
- total organizations: `<n>`
- enabled organizations (visibility=1): `<n>`
- UI verification needed: yes/no
- Final result: success/fail
