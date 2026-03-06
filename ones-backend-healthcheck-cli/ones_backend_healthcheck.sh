#!/usr/bin/env bash
set -euo pipefail

NS="${NS:-ones}"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="${OUT:-/tmp/ones_healthcheck_${TS}.log}"

# 可选：传入 BASEURL 做入口探测（例如 https://ones.example.com）
BASEURL="${BASEURL:-}"
# 可选：当发现异常Pod时，自动执行三板斧（describe/logs/previous）
COLLECT_ON_FAIL="${COLLECT_ON_FAIL:-1}"
# 默认仅检查最近 180 分钟（3小时）的 Warning 事件
SINCE_MINUTES="${SINCE_MINUTES:-180}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --since-minutes)
      SINCE_MINUTES="$2"
      shift 2
      ;;
    --since-minutes=*)
      SINCE_MINUTES="${1#*=}"
      shift
      ;;
    *)
      echo "[WARN] unknown arg: $1 (ignored)" | tee -a "$OUT"
      shift
      ;;
  esac
done

if ! [[ "$SINCE_MINUTES" =~ ^[0-9]+$ ]]; then
  echo "[FAIL] invalid --since-minutes: $SINCE_MINUTES" | tee "$OUT"
  exit 2
fi

echo "[INFO] ONES backend healthcheck start: $(date '+%F %T')" | tee "$OUT"
echo "[INFO] namespace=$NS" | tee -a "$OUT"

echo "[INFO] collect_on_fail=$COLLECT_ON_FAIL" | tee -a "$OUT"
echo "[INFO] since_minutes=$SINCE_MINUTES" | tee -a "$OUT"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "[FAIL] kubectl not found" | tee -a "$OUT"
  exit 2
fi

if ! kubectl get ns "$NS" >/dev/null 2>&1; then
  echo "[FAIL] namespace '$NS' not found" | tee -a "$OUT"
  exit 2
fi

pass=0
warn=0
fail=0

section() {
  echo -e "\n===== $* =====" | tee -a "$OUT"
}

ok() { echo "[PASS] $*" | tee -a "$OUT"; pass=$((pass+1)); }
ng() { echo "[FAIL] $*" | tee -a "$OUT"; fail=$((fail+1)); }
wm() { echo "[WARN] $*" | tee -a "$OUT"; warn=$((warn+1)); }

triage_pod() {
  local pod="$1"

  section "triage pod: $pod"

  echo "--- describe $pod ---" | tee -a "$OUT"
  kubectl -n "$NS" describe pod "$pod" >> "$OUT" 2>&1 || true

  echo "--- events for $pod ---" | tee -a "$OUT"
  kubectl -n "$NS" get events --field-selector "involvedObject.kind=Pod,involvedObject.name=${pod}" --sort-by=.lastTimestamp >> "$OUT" 2>&1 || true

  local containers
  containers="$(kubectl -n "$NS" get pod "$pod" -o jsonpath='{.spec.containers[*].name}' 2>/dev/null || true)"

  if [[ -z "$containers" ]]; then
    wm "cannot resolve containers for $pod, skip logs"
    return
  fi

  for c in $containers; do
    echo "--- logs (tail=200) pod=$pod container=$c ---" | tee -a "$OUT"
    kubectl -n "$NS" logs "$pod" -c "$c" --tail=200 >> "$OUT" 2>&1 || true

    echo "--- previous logs (tail=200) pod=$pod container=$c ---" | tee -a "$OUT"
    kubectl -n "$NS" logs "$pod" -c "$c" --previous --timestamps --tail=200 >> "$OUT" 2>&1 || true
  done
}

section "cluster basic"
kubectl get ns | tee -a "$OUT"

section "pod overview ($NS)"
kubectl -n "$NS" get po -o wide | tee -a "$OUT"

section "non-running/completed pods"
NONRUNNING="$(kubectl -n "$NS" get po --no-headers | awk '$3!="Running" && $3!="Completed" {print $1" "$3}')"
if [[ -z "$NONRUNNING" ]]; then
  ok "all pods are Running/Completed"
else
  ng "found abnormal pods"
  echo "$NONRUNNING" | tee -a "$OUT"

  if [[ "$COLLECT_ON_FAIL" == "1" ]]; then
    while read -r pod status; do
      [[ -z "${pod:-}" ]] && continue
      triage_pod "$pod"
    done <<< "$NONRUNNING"
  else
    wm "COLLECT_ON_FAIL=0, skip triage collection"
  fi
fi

section "warning events check ($NS, last ${SINCE_MINUTES}m)"
set +e
if command -v python3 >/dev/null 2>&1; then
  WARN_EVENTS="$(kubectl -n "$NS" get events --field-selector type=Warning -o json 2>/dev/null | python3 - "$SINCE_MINUTES" <<'PY'
import json,sys
from datetime import datetime, timedelta, timezone

since_min = int(sys.argv[1])
raw = sys.stdin.read().strip()
if not raw:
    sys.exit(0)

data = json.loads(raw)
items = data.get("items", [])
cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_min)

def parse_ts(s):
    if not s:
        return None
    # k8s timestamp like 2026-02-26T06:11:12Z
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None

rows = []
for e in items:
    ts = parse_ts(e.get("eventTime")) or parse_ts(e.get("lastTimestamp")) or parse_ts(e.get("firstTimestamp"))
    if not ts or ts < cutoff:
        continue
    obj = e.get("involvedObject", {})
    rows.append((
        ts,
        e.get("type", ""),
        e.get("reason", ""),
        obj.get("kind", ""),
        obj.get("name", ""),
        (e.get("message", "") or "").replace("\n", " ")
    ))

rows.sort(key=lambda x: x[0])
for r in rows[-20:]:
    print(f"{r[0].strftime('%Y-%m-%dT%H:%M:%SZ')}\t{r[1]}\t{r[2]}\t{r[3]}/{r[4]}\t{r[5]}")
PY
)"
else
  WARN_EVENTS="$(kubectl -n "$NS" get events --field-selector type=Warning --sort-by=.lastTimestamp 2>/dev/null | tail -n 20)"
fi
set -e

if [[ -n "$WARN_EVENTS" ]]; then
  wm "found Warning events in last ${SINCE_MINUTES}m (showing last 20)"
  echo "$WARN_EVENTS" | tee -a "$OUT"
else
  ok "no Warning events found in last ${SINCE_MINUTES}m"
fi

section "restarts (current snapshot)"
kubectl -n "$NS" get po --no-headers | awk '{print $1, $4}' | tee -a "$OUT"

# 链路关键组件（按 opsdoc 思路）
section "key chain checks"
checks=(
  "project-api"
  "project-web"
  "wiki-api|wiz"
  "mysql|mysql-cluster"
  "redis"
  "kafka|clickhouse|audit-log|ones-canal|binlog-event-sync"
  "kilob-sync|advanced-tidb|tikv|tidb"
  "performance-api|ones-bi-sync"
  "ones-platform-api|plugin-runtime|plugin-service-proxy"
)

for p in "${checks[@]}"; do
  echo "--- pattern: $p" | tee -a "$OUT"
  if kubectl -n "$NS" get po | grep -Ei "$p" | tee -a "$OUT"; then
    ok "match found for '$p'"
  else
    wm "no pod matched '$p' (maybe feature not enabled)"
  fi
done

section "resource snapshot"
if kubectl top node >/dev/null 2>&1; then
  kubectl top node | tee -a "$OUT"
  ok "node resource metrics available"
else
  wm "kubectl top node unavailable"
fi

if kubectl -n "$NS" top po >/dev/null 2>&1; then
  kubectl -n "$NS" top po | tee -a "$OUT"
  ok "pod resource metrics available"
else
  wm "kubectl top pod unavailable"
fi

section "telemetry namespace"
if kubectl get ns ones-telemetry >/dev/null 2>&1; then
  kubectl -n ones-telemetry get po | tee -a "$OUT"
  ok "ones-telemetry exists"
else
  wm "ones-telemetry not found"
fi

section "optional ingress/baseurl check"
if [[ -n "$BASEURL" ]]; then
  if command -v curl >/dev/null 2>&1; then
    set +e
    curl -kIsS --max-time 10 "$BASEURL" | head -n 1 | tee -a "$OUT"
    curl -kfsS --max-time 10 "$BASEURL/project/api/project/version" | tee -a "$OUT"
    rc=$?
    set -e
    if [[ $rc -eq 0 ]]; then
      ok "baseurl reachable and version API returned"
    else
      ng "baseurl/version api check failed: $BASEURL"
    fi
  else
    wm "curl not found, skip baseurl check"
  fi
else
  wm "BASEURL not provided, skip ingress/api probe"
fi

section "summary"
echo "PASS=$pass WARN=$warn FAIL=$fail" | tee -a "$OUT"
if [[ $fail -gt 0 ]]; then
  echo "RESULT=UNHEALTHY" | tee -a "$OUT"
  exit 1
fi

echo "RESULT=HEALTHY(with or without WARN)" | tee -a "$OUT"
echo "[INFO] report: $OUT" | tee -a "$OUT"
