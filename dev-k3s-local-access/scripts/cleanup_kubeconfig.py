#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run(cmd):
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout


def run_optional(cmd):
    p = subprocess.run(cmd, text=True, capture_output=True)
    return p.returncode == 0, (p.stdout + p.stderr).strip()


def load_config(kubeconfig: str):
    out = run(["kubectl", "--kubeconfig", kubeconfig, "config", "view", "-o", "json"])
    return json.loads(out)


def analyze(cfg):
    clusters = {c.get("name") for c in cfg.get("clusters", []) if c.get("name")}
    users = {u.get("name") for u in cfg.get("users", []) if u.get("name")}
    contexts = cfg.get("contexts", [])
    current = cfg.get("current-context", "")

    bad_contexts = []
    referenced_clusters = set()
    referenced_users = set()

    for c in contexts:
        name = c.get("name")
        ctx = c.get("context", {})
        cl = ctx.get("cluster")
        us = ctx.get("user")
        missing = []
        if cl and cl not in clusters:
            missing.append(f"cluster:{cl}")
        if us and us not in users:
            missing.append(f"user:{us}")
        if missing:
            bad_contexts.append((name, missing))
        if cl:
            referenced_clusters.add(cl)
        if us:
            referenced_users.add(us)

    orphan_clusters = sorted(clusters - referenced_clusters)
    orphan_users = sorted(users - referenced_users)
    return {
        "current": current,
        "bad_contexts": bad_contexts,
        "orphan_clusters": orphan_clusters,
        "orphan_users": orphan_users,
        "context_names": [c.get("name") for c in contexts if c.get("name")],
    }


def connectivity_check(kubeconfig: str, contexts: list[str], timeout: str):
    failed = []
    for name in contexts:
        ok, _ = run_optional([
            "kubectl",
            "--kubeconfig",
            kubeconfig,
            "--context",
            name,
            f"--request-timeout={timeout}",
            "get",
            "--raw=/readyz",
        ])
        if not ok:
            failed.append(name)
    return failed


def delete_item(kubeconfig: str, kind: str, name: str):
    if kind == "context":
        run(["kubectl", "--kubeconfig", kubeconfig, "config", "delete-context", name])
    elif kind == "cluster":
        run(["kubectl", "--kubeconfig", kubeconfig, "config", "delete-cluster", name])
    elif kind == "user":
        run(["kubectl", "--kubeconfig", kubeconfig, "config", "unset", f"users.{name}"])
    else:
        raise RuntimeError(f"unknown delete kind: {kind}")


def main():
    parser = argparse.ArgumentParser(
        description="Find and optionally clean invalid kubeconfig entries without touching valid clusters."
    )
    parser.add_argument("--kubeconfig", default=str(Path.home() / ".kube" / "config"), help="Target kubeconfig path")
    parser.add_argument("--check-connectivity", action="store_true", help="Also mark contexts failing /readyz as stale candidates")
    parser.add_argument("--timeout", default="3s", help="Timeout for connectivity checks, e.g. 3s")
    parser.add_argument("--allow-delete-current", action="store_true", help="Allow deletion if current-context is invalid")
    parser.add_argument("--dry-run", action="store_true", help="Explicitly run in dry-run mode")
    parser.add_argument("--apply", action="store_true", help="Apply cleanup. Default is dry-run")
    args = parser.parse_args()

    if args.dry_run and args.apply:
        print("[ERROR] --dry-run and --apply cannot be used together", file=sys.stderr)
        sys.exit(1)

    kubeconfig = os.path.expanduser(args.kubeconfig)
    if not os.path.exists(kubeconfig):
        print(f"[ERROR] kubeconfig not found: {kubeconfig}", file=sys.stderr)
        sys.exit(1)

    try:
        cfg = load_config(kubeconfig)
        report = analyze(cfg)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    current = report["current"]
    bad_contexts = report["bad_contexts"]
    orphan_clusters = report["orphan_clusters"]
    orphan_users = report["orphan_users"]

    stale_contexts = []
    if args.check_connectivity:
        try:
            stale_contexts = connectivity_check(kubeconfig, report["context_names"], args.timeout)
        except Exception as e:
            print(f"[WARN] connectivity check failed: {e}")

    print("[REPORT] invalid contexts:")
    if bad_contexts:
        for name, missing in bad_contexts:
            print(f"- {name}: missing {', '.join(missing)}")
    else:
        print("- none")

    print("[REPORT] orphan clusters:")
    if orphan_clusters:
        for name in orphan_clusters:
            print(f"- {name}")
    else:
        print("- none")

    print("[REPORT] orphan users:")
    if orphan_users:
        for name in orphan_users:
            print(f"- {name}")
    else:
        print("- none")

    if args.check_connectivity:
        print("[REPORT] connectivity-failed contexts (candidate only):")
        if stale_contexts:
            for name in stale_contexts:
                print(f"- {name}")
        else:
            print("- none")

    if not args.apply:
        print("[DRY-RUN] no changes applied")
        return

    to_delete_contexts = [name for name, _ in bad_contexts]
    if current and not args.allow_delete_current and current in to_delete_contexts:
        print(
            f"[ERROR] current-context '{current}' is invalid but deletion is blocked. Use --allow-delete-current.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        for name in to_delete_contexts:
            delete_item(kubeconfig, "context", name)
            print(f"[APPLY] deleted context: {name}")

        for name in orphan_clusters:
            delete_item(kubeconfig, "cluster", name)
            print(f"[APPLY] deleted cluster: {name}")

        for name in orphan_users:
            delete_item(kubeconfig, "user", name)
            print(f"[APPLY] deleted user: {name}")
    except Exception as e:
        print(f"[ERROR] apply failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("[OK] cleanup applied")


if __name__ == "__main__":
    main()
