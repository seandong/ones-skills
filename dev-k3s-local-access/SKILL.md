---
name: dev-k3s-local-access
description: Safely configure local kubectl access to a Huawei Cloud dev k3s cluster by exporting remote kubeconfig, starting kubectl proxy on port 8080, and incrementally upserting a dedicated context into local ~/.kube/config without overwriting existing clusters. Use this skill when tasks mention connecting local machine to dev k3s, repairing local kubectl connectivity to Huawei dev cluster, adding a new kube context safely, or cleaning invalid kubeconfig entries.
---

# Dev K3s Local Access

Use this skill to connect local `kubectl` to Huawei Cloud dev k3s without breaking existing kubeconfig entries.

## Preconditions

1. Ensure local `kubectl` is installed.

```bash
brew install kubectl
```

2. Ensure you can log in to target dev server and run `kubectl` there.

## Safe Workflow (No Overwrite)

1. On remote dev server, export raw kubeconfig and start proxy on fixed port `8080`.

```bash
kubectl config view --raw > /tmp/dev-k3s-remote-config.yaml

# Keep this running in background. If access fails later, rerun.
kubectl proxy --port=8080 --address=0.0.0.0 --accept-hosts='^.*$' --disable-filter=true &
```

2. Record your personal ones URL, for example:

```text
https://hsdev.k3s-dev.myones.net/
```

3. Copy remote config file to local machine (any secure path), then run safe upsert script.

```bash
python scripts/upsert_dev_k3s_context.py \
  --remote-kubeconfig /path/to/dev-k3s-remote-config.yaml \
  --ones-url https://hsdev.k3s-dev.myones.net \
  --context-name dev-k3s \
  --cluster-name dev-k3s \
  --user-name dev-k3s
```

Behavior:
- Do not overwrite the full `~/.kube/config`.
- Only upsert named `cluster/user/context` entries.
- Auto-create a backup when target kubeconfig already exists.

4. Verify with explicit context.

```bash
kubectl --context dev-k3s get po -n ones | grep project-api
```

## Cleanup Invalid Local Kubeconfig Entries

1. Run dry-run report first (no changes):

```bash
python scripts/cleanup_kubeconfig.py --dry-run
```

2. Optional: include connectivity checks (stale candidates only):

```bash
python scripts/cleanup_kubeconfig.py \
  --dry-run \
  --check-connectivity \
  --timeout 3s
```

3. Apply cleanup after review:

```bash
python scripts/cleanup_kubeconfig.py --apply
```

Notes:
- Cleanup removes invalid contexts (missing cluster/user references).
- Cleanup removes orphan clusters/users not referenced by any context.
- Current context is protected by default; use `--allow-delete-current` only when intentional.

## Troubleshooting

- If cluster becomes unreachable, rerun remote proxy command:

```bash
kubectl proxy --port=8080 --address=0.0.0.0 --accept-hosts='^.*$' --disable-filter=true &
```

- If TLS/auth errors appear, rerun upsert script with correct `--ones-url` and fresh remote kubeconfig export.

## Safety Rules

- Never commit `~/.kube/config` or certificate/key data to git.
- Keep proxy port fixed at `8080` for this workflow.
- Always dry-run cleanup before `--apply`.

## Resources

- Script: `scripts/upsert_dev_k3s_context.py`
- Script: `scripts/cleanup_kubeconfig.py`
