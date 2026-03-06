---
name: ones-k3s-open-telemetry-cli
description: 在 ONES 单机版 K3S 环境按 open-telemetry.md 开启可观测性（Telemetry/Grafana），支持已开启核验、未开启安装、访问连通性验证与回滚。用户提到“开启监控/打开监控/开启 telemetry/grafana 31380”时使用。
---

# ONES K3S 开启监控（Telemetry）

## 参考文档
- 主文档：`/Users/caixin/vscode/ops-doc/ops/docs/matching/K3S/open-telemetry.md`

## 适用场景
- 用户要求在 K3S ONES 环境“开启监控/打开监控”。
- 用户要求核验监控是否已开启，或修复无法访问 Grafana（31380）问题。

## 前置条件
- 可 SSH 免密登录目标主机（优先 `root@<ip>`）。
- 目标主机可执行 `kubectl`，且存在 `ones-installer` 命名空间。
- 了解“配置应用”可能触发组件重建，需在可接受窗口执行。

## 执行策略（先查后改）
1. 先核验是否已开启，不要直接重装。
2. 只有在 `ones-telemetry` 不存在或 Grafana NodePort 缺失时再改配置并安装。
3. 生效后必须同时验证资源状态与访问状态。

## 标准流程

### 1) 登录与现状核验
```bash
ssh root@<ip> '
  echo host=$(hostname) user=$(whoami)
  kubectl get ns ones-telemetry >/dev/null 2>&1 && echo ns=exists || echo ns=missing
  kubectl get svc -n ones-telemetry 2>/dev/null | egrep -i "NAME|grafana|otlp" || true
'
```

判定：
- 若 `ones-telemetry` 存在且有 `grafana-nodeport`（通常 `80:31380`），进入“访问验证”。
- 若不存在，执行第 2 步安装。

### 2) 在 installer-api 容器内写入配置并生效
```bash
ssh root@<ip> 'bash -s' <<'EOF_REMOTE'
set -euo pipefail
POD=$(kubectl get po -n ones-installer -l app=installer-api --sort-by='{.metadata.creationTimestamp}' -o jsonpath='{.items[-1].metadata.name}')
kubectl exec -n ones-installer "$POD" -c installer-api -- bash -lc '
set -euo pipefail
cd /data/ones/ones-ai-k8s
cp config/private.yaml config/private.yaml.bak.$(date +%Y%m%d%H%M%S)

grep -q "^onesTelemetryClickhouseEnable:" config/private.yaml || echo "onesTelemetryClickhouseEnable: true" >> config/private.yaml
grep -q "^otlpExportGrpcAddr:" config/private.yaml || echo "otlpExportGrpcAddr: \"otlp-collector-service.ones-telemetry:4317\"" >> config/private.yaml
grep -q "^grafanaLocalNodePort:" config/private.yaml || echo "grafanaLocalNodePort: \"31380\"" >> config/private.yaml

grep -q "^grafanaLocalHost:" config/private.yaml \
  && sed -i.bak "s#^grafanaLocalHost:.*#grafanaLocalHost: \"<ip>:31380\"#" config/private.yaml \
  || echo "grafanaLocalHost: \"<ip>:31380\"" >> config/private.yaml

grep -q "^onesTelemetryExportEndpoint:" config/private.yaml || echo "onesTelemetryExportEndpoint: \"https://hybridcloud.ones.cn/telemetry/otlp/\"" >> config/private.yaml
grep -q "^onesTelemetryExportLogEnabled:" config/private.yaml || echo "onesTelemetryExportLogEnabled: true" >> config/private.yaml

egrep -n "onesTelemetryExportEndpoint|onesTelemetryExportLogEnabled|onesTelemetryClickhouseEnable|otlpExportGrpcAddr|grafanaLocalNodePort|grafanaLocalHost" config/private.yaml

make setup-ones-telemetry
make setup-ones
'
kubectl get pod -n ones-telemetry
EOF_REMOTE
```

说明：
- `<ip>` 必须替换为实际服务器 IP。
- `make setup-ones` 输出中出现旧资源删除日志可能是预期行为，需结合最终 Pod 状态判断成功与否。

### 3) 访问验证
```bash
# 服务器本机验证（200/301 都可接受）
ssh root@<ip> 'curl -sSI --max-time 8 http://127.0.0.1:31380 | head -n 5'

# 资源验证
ssh root@<ip> 'kubectl get svc -n ones-telemetry | egrep -i "grafana|otlp"'
ssh root@<ip> 'kubectl get pod -n ones-telemetry | egrep "grafana|otlp|ones-logging"'
```

## 失败处理
- `Permission denied (publickey)`：更换可用用户、检查私钥与远端 `authorized_keys`。
- `Operation not permitted`（22 端口）：申请网络放行后重试。
- `31380` 不通：先测服务器本机 `127.0.0.1:31380`，再检查 NodePort、主机防火墙和网络策略。
- Pod 未就绪：重点看 `grafana-deployment`、`otlp-collector`、`ones-logging` 的 READY/STATUS。

## 输出要求
每次执行后必须给出：
1. 是否已开启（是/否）
2. 关键证据（ns、svc、pod、curl 结果）
3. 访问地址（`http://<ip>:31380` 或 `http://<ip>:31380/grafana/`）
4. 若失败：明确卡点与下一步最小动作
