---
name: ones-backend-healthcheck-cli
description: 在 ONES 单机/集群（K3S/K8S）环境执行后端健康巡检并输出结论。用于“检查ONES后端是否正常”“巡检Pod异常”“检查Warning Events”“验证域名与version接口可达性”“异常Pod自动三板斧采集（describe/logs/previous）”等场景。
---

# ONES Backend Healthcheck (CLI)

使用本技能统一执行 ONES 后端巡检，优先复用脚本，避免手工漏项。

## 1) 执行前检查

- 确认可在目标环境执行 `kubectl`。
- 默认命名空间为 `ones`，可用环境变量 `NS` 覆盖。

## 2) 标准执行

在本技能目录运行：

```bash
bash scripts/ones_backend_healthcheck.sh
```

常用参数：

```bash
# 带入口探测（首页 + /project/api/project/version）
BASEURL="http://<host>:30011" bash scripts/ones_backend_healthcheck.sh

# 仅看最近N分钟 Warning Events（默认180分钟=3小时）
bash scripts/ones_backend_healthcheck.sh --since-minutes 180

# 异常时是否自动采集三板斧（默认1开启）
COLLECT_ON_FAIL=1 bash scripts/ones_backend_healthcheck.sh
```

## 3) 巡检覆盖项

- 集群基础与命名空间可用性
- `ones` 命名空间 Pod 总览、非 Running/Completed 异常检测
- 异常 Pod 自动采集：
  - `describe pod`
  - 容器 `logs --tail=200`
  - 容器 `logs --previous --timestamps --tail=200`
  - Pod 级 events（involvedObject.name 过滤）
- 命名空间 Warning Events 窗口检查（默认最近 3 小时）
- 关键链路组件匹配检查（project/wiki/mysql/redis/kafka/clickhouse/search/performance/plugin）
- 资源快照（`kubectl top node/pod`，若可用）
- `ones-telemetry` 运行状态
- 可选入口可达性与 version API 校验

## 4) 结果判定

- 以脚本 summary 为准：`PASS/WARN/FAIL` 与 `RESULT`。
- `FAIL>0` 视为不健康，需要优先处理失败项。
- 出现 `WARN` 时结合事件与重启信息评估是否需跟进。

## 5) 输出与回传

- 脚本会输出报告文件：`/tmp/ones_healthcheck_YYYYmmdd_HHMMSS.log`。
- 对用户回复时优先给出：
  - 最终结论（HEALTHY/UNHEALTHY）
  - 关键异常（异常 Pod、Warning Events、入口/API失败）
  - 报告路径
