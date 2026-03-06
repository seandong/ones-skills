---
name: ones-k3s-backup-cli
description: Enable and verify ONES single-node K3S backup (MinIO/clickhouse/mysql/mc) by following backup-Instructions.md, with non-interactive execution, manual backup trigger, and evidence-based checks.
---

# ONES K3S Backup CLI (Strict-Doc + Token-Efficient)

Follow these docs strictly and in order:
- `https://opsdoc.ones.cn/docs/data/K3S/single-node-backup/install-minio`
- `https://opsdoc.ones.cn/docs/data/K3S/single-node-backup/backup-Instructions`

## Required runtime inputs (must be provided each run)

- `LOGIN_METHOD` (for example: `ssh root@<host>`)

Required for this skill run (do not skip):

- `ONES_AIK8S_DIR` (default `/data/ones/ones-ai-k8s`)
- `MINIO_ACCESS_KEY` (default `miniouser`)
- `MINIO_SECRET_KEY` (default from `config/private.yaml`)
- `MINIO_DATA_HOST_PATH` (maps to `onesBackupInternalMinioUserDefinedDataHostPath`, must be explicitly set per install-minio 2.2)

## Hard rules

1. **Strict order**: configure first, then apply, then manual backup trigger, then file evidence checks.
2. **Non-interactive first**: prefer `kubectl exec ... -- sh -lc` and non-TTY execution.
3. **Exception handling**: on any command error, stop current phase, report summary + log path, wait for user confirmation.
4. **Token-efficient output**: full logs stay on remote `/tmp/ones-backup-*.log`; only return key evidence lines.
5. **Version-aware config**:
- For `6.33+`, use `backupS3Endpoint/backupS3AccessKeyID/backupS3SecretAccessKey` and `backupEnabledForObjectStorage`.
- For `6.1.94+`, use ClickHouse backup (not kafka backup).
6. **install-minio 2.2 enforcement**: `onesBackupInternalMinioUserDefinedDataHostPath` is mandatory in this skill (not optional). Validate host path exists and is writable before `make setup-ones-backup`.

## Workflow

### Phase 0: Precheck

- Ensure cluster reachable.
- Detect installer pod and working dir:
- `POD=$(kubectl -n ones-installer get pods | awk '/installer-api/{print $1; exit}')`
- Verify `ONES_AIK8S_DIR` exists in pod.
- Verify `MINIO_DATA_HOST_PATH` exists on host and is writable (create with correct ownership/permissions if missing).

Report:
- host, installer pod, ones version, k3s single-node assumption.

### Phase 1: Deploy/verify backup MinIO (Chapter 2 install-minio)

For `6.33+` internal MinIO:

- Update `config/private.yaml` keys:
- `onesBackupInternalMinioRootUser`
- `onesBackupInternalMinioRootPassword`
- `onesBackupInternalMinioUserDefinedDataHostPath` (**required**, value comes from `MINIO_DATA_HOST_PATH`)
- Apply:
- `make setup-ones-backup`
- Verify:
- `kubectl -n ones-backup get po -l app=minio -w`
- `curl http://<IP>:31901` (or `curl -I ...`)

### Phase 2: Enable backup switches (backup-Instructions 1.x)

For `6.33+` and `6.1.94+`, set in `config/private.yaml`:

- MinIO/S3:
- `backupS3Endpoint: http://minio.ones-backup:9000`
- `backupS3AccessKeyID: <MinIO access key>`
- `backupS3SecretAccessKey: <MinIO secret key>`
- optional `backupS3ForcePathStyle: true`

- ClickHouse:
- `clickhouseBackupEnable: 'true'`
- `clickhouseBackupCleanEnable: "true"`
- `clickhouseBackupCleanDaysMinAge: "60"`

- MySQL (internal DB only):
- `mysqlXbackupEnable: true`
- `mysqlStatusServerEnable: true`
- `mysqlXbackupToken: "<random-token>"`
- `xbackupNginxEnable: true`
- `xbackupNginxBasicAuthUser: "<user>"`
- `xbackupNginxBasicAuthPasswordSecret: "<htpasswd-md5-hash>"`
- `mysqlXbackupInternalEnable: true`
- `mysqlXbackupNginxBasicAuthPassword: <plain-password>`
- `mysqlXbackupcleanBackupMinAge: "180d"`
- `mysqlXbackupServerInstance: master`

- Attachments:
- `backupEnabledForObjectStorage: 'true'`

Apply changes:

- `make setup-ones SKIP_DIFF=true`
- `make setup-ones-built-in-mysql SKIP_DIFF=true`

Status checks:

- `kubectl get pod -A|grep -iE 'clickhouse-backup|kafka'`
- `kubectl -n ones get po | grep mysql`
- `kubectl get po -n ones -l app=mc-backup-tools`

Critical consistency checks (must pass before Phase 3):

- Verify MinIO runtime credentials match `private.yaml` backup S3 credentials:
  - `ones-backup` secret root user/password == `backupS3AccessKeyID/backupS3SecretAccessKey` effective values.
- Verify ClickHouse/MySQL backup ConfigMaps currently mounted by running pods are the latest (not stale leftovers).
- If stale/empty endpoint config exists (e.g. `http://:9000`), clean old CM and re-apply before manual backup.

### Phase 3: Run manual backups (backup-Instructions 2.x)

- ClickHouse manual backup:
- `make backup-clickhouse-now`
- Success evidence: log contains `BACKUP_CREATED`.

- MySQL manual full backup:
- `make mysql-base-backup NAMESPACE=ones`
- `make logs-mysql-xbackup NAMESPACE=ones TAIL=200`
- `make checkprocess-mysql-xbackup-policy NAMESPACE=ones`
- Success evidence: log contains `备份成功` or successful backup metadata entry.

- Attachment/object backup validation:
- For legacy mode with mc tool enabled: `make mc-backup-tools NAMESPACE=ones`
- For 6.33+ object-storage mode: do **not** fail only because `mc-backup-tools`/`onesfile-backup` are `0/0`; use object artifacts in MinIO as success evidence.

### Phase 4: Backup file evidence checks (backup-Instructions 3.x)

- Confirm MinIO path:
- `kubectl describe pod -n ones-backup minio-0 | grep Path:`

- Check file artifacts:
- ClickHouse: `ls -altr /data/ones/minio/data/clickhouse-backup/*/*/*`
- MySQL: `ls -altr /data/ones/minio/data/mysql-xbackup/`
- mc: `du -sh /data/ones/minio/data/ones-private-files-backup/ /data/ones/minio/data/ones-public-files-backup/`

## Common pitfalls and fixes

1. **MySQL backup 401 Unauthorized (`/infrastructure/mysql-status/status`)**
- Usually caused by xbackup auth mismatch or stale config not applied.
- Fix sequence:
- ensure `xbackupNginxBasicAuthUser` and `mysqlXbackupNginxBasicAuthPassword` match;
- ensure `xbackupNginxBasicAuthPasswordSecret` is valid htpasswd-md5 hash;
- rerun `make setup-ones SKIP_DIFF=true` and `make setup-ones-built-in-mysql SKIP_DIFF=true`;
- retry `make mysql-base-backup NAMESPACE=ones`.

2. **Hash string mangled by shell (`$apr1...`)**
- When writing `xbackupNginxBasicAuthPasswordSecret`, avoid shell variable expansion.
- Prefer editing file with a script that writes literal text, or single-quote the whole hash carefully.

3. **Pods restarting after apply**
- `Terminating/PodInitializing` is expected briefly.
- Wait until target pods are `Running` before connectivity checks.

4. **ClickHouse backup error: `Host is empty in S3 URI`**
- Usually stale/invalid endpoint config is mounted (often old ConfigMap with empty host).
- Fix sequence:
  - verify `backupS3Endpoint` in `private.yaml` is valid (e.g. `http://minio.ones-backup:9000`),
  - identify active CM used by clickhouse-backup pod,
  - remove stale CM with empty endpoint and re-apply `setup-ones`,
  - rerun `make backup-clickhouse-now`.

5. **MySQL backup error: `InvalidAccessKeyId` / `failed to make a backup`**
- Usually MinIO runtime credentials and backup S3 credentials are inconsistent.
- Fix sequence:
  - align MinIO secret and `backupS3AccessKeyID/backupS3SecretAccessKey`,
  - rerun `make setup-ones SKIP_DIFF=true` and `make setup-ones-built-in-mysql SKIP_DIFF=true`,
  - rerun mysql manual backup and verify logs.

## 5-minute progress report format

- 当前步骤: `<phase>`
- 是否报错: `否/是（简述）`
- 下一步: `<next action>`
- 关键日志: `<remote log path>`

## Completion report template

- Host/Login: `<LOGIN_METHOD>`
- MinIO deployment: success/fail (pod + nodeport evidence)
- Config apply:
- `setup-ones`: success/fail
- `setup-ones-built-in-mysql`: success/fail
- Manual backups:
- ClickHouse: success/fail (evidence)
- MySQL: success/fail (evidence)
- mc: success/fail (evidence)
- Backup files:
- clickhouse-backup path check: yes/no
- mysql-xbackup path check: yes/no
- object buckets size check: yes/no
- Exceptions and manual confirmations
- Final result: success/fail
