#!/usr/bin/env python3
import argparse
import base64
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


def run(cmd):
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout


def normalize_server(domain_or_url: str) -> str:
    s = domain_or_url.strip()
    if not s:
        raise ValueError("ones domain/url is required")

    if "://" not in s:
        s = f"https://{s}"
    parsed = urlparse(s)
    if not parsed.hostname:
        raise ValueError(f"invalid domain/url: {domain_or_url}")
    return f"https://{parsed.hostname}:6443"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def backup_if_exists(path: Path) -> Path | None:
    if not path.exists():
        return None
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.bak.{ts}")
    shutil.copy2(path, backup)
    return backup


def get_remote_user_data(remote_kubeconfig: str):
    data = run([
        "kubectl",
        "--kubeconfig",
        remote_kubeconfig,
        "config",
        "view",
        "--raw",
        "-o",
        "json",
    ])
    cfg = json.loads(data)
    users = cfg.get("users", [])
    if not users:
        raise RuntimeError("no users found in remote kubeconfig")
    user = users[0].get("user", {})
    cert = user.get("client-certificate-data")
    key = user.get("client-key-data")
    if not cert or not key:
        raise RuntimeError("remote kubeconfig missing client-certificate-data/client-key-data")
    return cert, key


def set_kubeconfig_entry(kubeconfig: str, cluster: str, user: str, context: str, server: str, cert: str, key: str):
    run([
        "kubectl",
        "--kubeconfig",
        kubeconfig,
        "config",
        "set-cluster",
        cluster,
        f"--server={server}",
        "--insecure-skip-tls-verify=true",
    ])

    cert_bytes = base64.b64decode(cert)
    key_bytes = base64.b64decode(key)
    with tempfile.NamedTemporaryFile(delete=False) as cert_file, tempfile.NamedTemporaryFile(delete=False) as key_file:
        cert_file.write(cert_bytes)
        key_file.write(key_bytes)
        cert_path = cert_file.name
        key_path = key_file.name

    try:
        os.chmod(cert_path, 0o600)
        os.chmod(key_path, 0o600)
        run([
            "kubectl",
            "--kubeconfig",
            kubeconfig,
            "config",
            "set-credentials",
            user,
            f"--client-certificate={cert_path}",
            f"--client-key={key_path}",
            "--embed-certs=true",
        ])
    finally:
        if os.path.exists(cert_path):
            os.remove(cert_path)
        if os.path.exists(key_path):
            os.remove(key_path)
    run([
        "kubectl",
        "--kubeconfig",
        kubeconfig,
        "config",
        "set-context",
        context,
        f"--cluster={cluster}",
        f"--user={user}",
    ])


def main():
    parser = argparse.ArgumentParser(
        description="Safely upsert a dev k3s context into local kubeconfig without overwriting existing clusters."
    )
    parser.add_argument("--remote-kubeconfig", required=True, help="Path to kubeconfig exported from remote server")
    parser.add_argument("--ones-url", required=True, help="Your ones domain or URL, e.g. hsdev.k3s-dev.myones.net")
    parser.add_argument("--kubeconfig", default=str(Path.home() / ".kube" / "config"), help="Target local kubeconfig path")
    parser.add_argument("--cluster-name", default="dev-k3s", help="Cluster name to write")
    parser.add_argument("--user-name", default="dev-k3s", help="User name to write")
    parser.add_argument("--context-name", default="dev-k3s", help="Context name to write")
    parser.add_argument("--set-current", action="store_true", help="Set current-context to the new context")
    args = parser.parse_args()

    target = Path(os.path.expanduser(args.kubeconfig))
    ensure_parent(target)

    try:
        server = normalize_server(args.ones_url)
        cert, key = get_remote_user_data(args.remote_kubeconfig)
        backup = backup_if_exists(target)
        set_kubeconfig_entry(
            str(target),
            args.cluster_name,
            args.user_name,
            args.context_name,
            server,
            cert,
            key,
        )
        if args.set_current:
            run([
                "kubectl",
                "--kubeconfig",
                str(target),
                "config",
                "use-context",
                args.context_name,
            ])
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print("[OK] upsert completed")
    print(f"kubeconfig: {target}")
    if backup:
        print(f"backup: {backup}")
    else:
        print("backup: (not needed, target did not exist)")
    print(f"context: {args.context_name}")
    print(f"server: {server}")
    print("next: kubectl --context {0} get po -n ones | grep project-api".format(args.context_name))


if __name__ == "__main__":
    main()
