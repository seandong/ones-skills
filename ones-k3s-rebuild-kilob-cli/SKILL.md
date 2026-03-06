---
name: ones-k3s-rebuild-kilob-cli
description: 在 ONES 单机版 K3S 环境执行 Kilob 索引重建、解锁、CDC 重建、PD/TiKV 异常修复与一致性核验。用于搜索/筛选异常、索引不一致、迁移后索引校验、kilob 报锁冲突等场景。
---

# ONES K3S 重建索引（Kilob）

按顺序执行。除非用户明确要求跳步，否则不要省略前置确认、日志判定与结果核验。

## 0) 命令入口（强约束）
优先使用：
```bash
./ones-ai-k8s.sh make <target>
```
不要在外层目录直接 `make <target>`（可能出现 `No rule to make target`）。

## 1) 前置判定
1. 进入目录并确认可执行：
```bash
cd /data/ones/ones-installer-pkg
ls ones-ai-k8s.sh
```
2. 读取版本（用于分支选择）：
```bash
grep -n '^onesVersion:' config/public.yaml
```
3. 读取当前重建参数：
```bash
grep -nE 'kilobSyncSchemaHash|kilobForceSnapshotVersion|kilobForceSnapshotAll' config/private.yaml
```

## 2) 标准重建主流程
1. 备份并递增参数（必须与上次不同）：
```bash
cp -a config/private.yaml config/private.yaml.bak.$(date +%F-%H%M%S)
# 修改为新值
kilobSyncSchemaHash: "<new>"
kilobForceSnapshotVersion: "<new>"
kilobForceSnapshotAll: "true"
```
2. 应用配置：
```bash
./ones-ai-k8s.sh make setup-ones
```
3. 跟踪日志：
```bash
kubectl logs -n ones -l app=kilob-sync --tail=200 -f
```

## 3) 完成判定（必须全部满足）
满足以下 3 条才算“重建完成”：
1. 日志出现并推进 `snapshot topic ... progress: 100%`（关键 topic）
2. 出现 `kilob_sync starts consuming incremental events`
3. 一致性核验通过（见第 6 节）

## 4) 锁冲突处理（FAQ 4.6，升级版）
当日志持续出现 `Retry to acquire the lock` 时，按以下串行流程执行：

1. 先停 kilob：
```bash
kubectl -n ones scale deployment kilob-sync-deployment --replicas=0
```
2. 删除锁：
```bash
kubectl exec -n ones stable-redis-master-0 -- redis-cli -n 11 del ones-cdc-lock
```
3. 确认锁已删除：
```bash
kubectl exec -n ones stable-redis-master-0 -- redis-cli -n 11 ttl ones-cdc-lock
# 期望 -2
```
4. 先恢复 CDC 相关，再恢复 kilob：
```bash
kubectl -n ones scale deployment kafka-cdc-connect-deployment --replicas=1
kubectl -n ones scale deployment binlog-event-sync-deployment --replicas=1
kubectl -n ones scale deployment ones-bi-sync-etl-deployment --replicas=1
kubectl -n ones scale deployment kilob-sync-deployment --replicas=1
```
5. 观察 8~10 分钟：若 `tries` 持续增长，判定 4.6 失败。

## 5) CDC 重建分支（FAQ 4.1）
- `onesVersion >= v6.18.40`：
```bash
./ones-ai-k8s.sh make rebuild-cdc
```
- `onesVersion < v6.18.40`：按文档手动 scale/delete topic/scale。

执行后重新走“第2节标准重建主流程”。

## 6) 一致性核验（必做）
### 6.1 高版本（推荐）
```bash
./ones-ai-k8s.sh make print-kilob-index
```
通过标准：
- `Full sync completed: [YES]`
- 表格中关键业务表无 `❌`

### 6.2 低版本
按文档使用 `kilob-cli print_index`。

## 7) 升级到高风险分支（FAQ 4.7）
满足任一条件才进入 4.7：
- 连续 2 次“4.1 + 第2节重建 + 4.6”后仍持续锁冲突
- `Retry to acquire the lock` 长时间持续，且无快照推进

⚠️ 4.7 为高风险操作，必须先让用户明确确认。

执行要点：
1. scale down：`kilob-sync`、`advanced-tidb-pd`、`advanced-tidb-tikv`
2. 备份并重建目录：
- `/data/ones/ones-local-storage/tidb/ones/pd-advanced-tidb-pd-0`
- `/data/ones/ones-local-storage/tidb/ones/tikv-advanced-tidb-tikv-0`
3. scale up：`advanced-tidb-pd`、`advanced-tidb-tikv`、`kilob-sync`
4. 再按第 3 节完成判定 + 第 6 节一致性核验

## 8) 关键词到分支映射
- `Retry to acquire the lock` → 第 4 节
- `raft entry is too large` → 调整 `raft-entry-max-size`（文档 4.4）
- `serialized which is larger` → 调整 `CONNECT_PRODUCER_MAX_REQUEST_SIZE`（文档 4.5）
- `loadRegion from PD failed` → 第 7 节（FAQ 4.7）

## 9) 输出模板（每轮必须给）
1. 本轮执行步骤（含命令入口）
2. 日志关键证据（复制关键行）
3. 当前判定（通过/失败/阻塞）
4. 下一步分支与风险等级（低/中/高）

## 10) 参考
- https://opsdoc.ones.cn/docs/data/K3S/rebuild-kilob
