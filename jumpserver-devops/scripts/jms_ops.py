#!/usr/bin/env python3
import argparse
import base64
import datetime
import hmac
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple

import requests

DEFAULT_BASE_URL = "https://devjumpserver.myones.net"
DEFAULT_ENV_FILE = os.path.expanduser("~/.onesdev.env")


class JmsError(Exception):
    pass


def _load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


class JumpServerClient:
    def __init__(self, base_url: str, access_key: str, secret_key: str, timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.access_key = access_key
        self.secret_key = secret_key
        self.timeout = timeout

    def _sign_headers(self, method: str, path_with_query: str, accept: str) -> Dict[str, str]:
        method = method.lower()
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        text = (
            f"(request-target): {method} {path_with_query}\n"
            f"accept: {accept}\n"
            f"date: {date}"
        )
        digest = hmac.new(self.secret_key.encode(), text.encode(), hashlib.sha256).digest()
        signature = base64.b64encode(digest).decode()
        auth = (
            f'Signature keyId="{self.access_key}",algorithm="hmac-sha256",'
            f'headers="(request-target) accept date",signature="{signature}"'
        )
        return {"Accept": accept, "Date": date, "Authorization": auth}

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        accept: str = "application/json",
    ) -> requests.Response:
        clean_path = path if path.startswith("/") else "/" + path
        filtered_params: Dict[str, Any] = {}
        if params:
            filtered_params = {k: v for k, v in params.items() if v is not None}
        query = urllib.parse.urlencode(filtered_params, doseq=True) if filtered_params else ""
        path_with_query = f"{clean_path}?{query}" if query else clean_path
        headers = self._sign_headers(method, path_with_query, accept)
        url = self.base_url + clean_path
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=filtered_params,
            json=json_body,
            timeout=self.timeout,
        )
        return resp


def _require_ok(resp: requests.Response, path: str) -> Dict[str, Any]:
    if 200 <= resp.status_code < 300:
        if "json" in (resp.headers.get("content-type", "").lower()):
            return resp.json()
        return {"raw": resp.text}
    snippet = resp.text[:300].replace("\n", " ")
    raise JmsError(f"request failed: {path} status={resp.status_code} body={snippet}")


def _output(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if isinstance(data, (dict, list)):
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(data)


def cmd_list_hosts(client: JumpServerClient, args: argparse.Namespace) -> int:
    params = {"search": args.search, "limit": args.limit, "offset": args.offset}
    obj = _require_ok(client.request("GET", "/api/v1/perms/users/assets/", params=params), "/api/v1/perms/users/assets/")
    rows = []
    for it in obj.get("results", []):
        rows.append(
            {
                "id": it.get("id"),
                "hostname": it.get("hostname"),
                "ip": it.get("ip"),
                "protocols": it.get("protocols"),
                "platform": it.get("platform"),
                "active": it.get("is_active"),
            }
        )
    _output({"count": obj.get("count", 0), "results": rows}, args.json)
    return 0


def cmd_list_system_users(client: JumpServerClient, args: argparse.Namespace) -> int:
    path = f"/api/v1/perms/users/assets/{args.asset_id}/system-users/"
    params = {"search": args.search, "limit": args.limit, "offset": args.offset}
    obj = _require_ok(client.request("GET", path, params=params), path)
    rows = []
    for it in obj.get("results", []):
        rows.append(
            {
                "id": it.get("id"),
                "name": it.get("name"),
                "username": it.get("username"),
                "protocol": it.get("protocol"),
                "actions": it.get("actions"),
            }
        )
    _output({"count": obj.get("count", 0), "results": rows}, args.json)
    return 0


def _create_connection_token(client: JumpServerClient, asset_id: str, system_user_id: str) -> Dict[str, Any]:
    path = "/api/v1/users/connection-token/client-url/"
    body = {"asset": asset_id, "system_user": system_user_id}
    obj = _require_ok(client.request("POST", path, json_body=body), path)
    url = obj.get("url")
    if not isinstance(url, str) or not url.startswith("jms://"):
        raise JmsError("connection token response does not contain jms:// url")

    payload_b64 = url[len("jms://") :]
    try:
        decoded = base64.b64decode(payload_b64).decode()
        outer = json.loads(decoded)
        inner = json.loads(outer.get("token", "{}"))
    except Exception as exc:
        raise JmsError(f"failed to parse connection token payload: {exc}") from exc

    return {
        "url": url,
        "filename": outer.get("filename"),
        "protocol": outer.get("protocol"),
        "login_user": outer.get("username"),
        "host": inner.get("ip"),
        "port": int(inner.get("port")) if str(inner.get("port", "")).isdigit() else inner.get("port"),
        "username": inner.get("username"),
        "password": inner.get("password"),
        "config": outer.get("config"),
        "expires_at": None,
    }


def _masked_password(password: Optional[str]) -> Optional[str]:
    if password is None:
        return None
    if len(password) <= 4:
        return "*" * len(password)
    return password[:2] + "*" * (len(password) - 4) + password[-2:]


def cmd_ssh_params(client: JumpServerClient, args: argparse.Namespace) -> int:
    data = _create_connection_token(client, args.asset_id, args.system_user_id)
    if not args.raw:
        data = dict(data)
        data["password"] = _masked_password(data.get("password"))
    _output(data, args.json)
    return 0


def cmd_ssh_connect(client: JumpServerClient, args: argparse.Namespace) -> int:
    data = _create_connection_token(client, args.asset_id, args.system_user_id)
    host = data.get("host")
    port = data.get("port")
    username = data.get("username")
    password = data.get("password")

    if not host or not port or not username:
        raise JmsError("missing ssh connection fields from connection token")

    if args.print_only:
        printable = dict(data)
        printable["password"] = _masked_password(password)
        _output(printable, args.json)
        return 0

    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-p", str(port), f"{username}@{host}"]
    sshpass_bin = shutil.which("sshpass")
    if password and sshpass_bin:
        run_cmd = [sshpass_bin, "-p", password] + ssh_cmd
        if args.json:
            _output({"command": run_cmd, "note": "using sshpass for non-interactive password login"}, True)
        return subprocess.call(run_cmd)

    if args.json:
        _output(
            {
                "note": "sshpass is not available or password missing; falling back to interactive ssh",
                "command": ssh_cmd,
                "password": _masked_password(password),
            },
            True,
        )
    else:
        print("sshpass not available or password missing; falling back to interactive ssh.")
        if password:
            print(f"Password (masked): {_masked_password(password)}")
            print("Use `ssh-params --raw` if you need the full password.")
        print("Command:", " ".join(ssh_cmd))
    return subprocess.call(ssh_cmd)


def cmd_run_command(client: JumpServerClient, args: argparse.Namespace) -> int:
    create_path = "/api/v1/ops/command-executions/"
    body = {"command": args.command, "run_as": args.system_user_id, "hosts": [args.asset_id]}
    created = _require_ok(client.request("POST", create_path, json_body=body), create_path)

    log_url = created.get("log_url")
    if not log_url:
        _output(created, args.json)
        return 0

    mark = ""
    start = time.time()
    chunks = []
    while time.time() - start <= args.timeout:
        params = {"mark": mark} if mark else None
        log_obj = _require_ok(client.request("GET", log_url, params=params), log_url)
        chunk = log_obj.get("data", "")
        if chunk:
            chunks.append(chunk)
            if not args.json:
                print(chunk, end="")
        mark = log_obj.get("mark", mark)
        if log_obj.get("end"):
            result = {
                "task_id": created.get("id"),
                "command": created.get("command"),
                "finished": True,
                "log": "".join(chunks),
                "log_url": log_url,
            }
            if args.json:
                _output(result, True)
            return 0
        time.sleep(args.poll_interval)

    result = {
        "task_id": created.get("id"),
        "command": created.get("command"),
        "finished": False,
        "timed_out": True,
        "timeout_seconds": args.timeout,
        "log": "".join(chunks),
        "log_url": log_url,
    }
    if args.json:
        _output(result, True)
    else:
        print(f"\nCommand log polling timed out after {args.timeout}s.")
        print(f"Task ID: {created.get('id')}")
        print(f"Log URL: {log_url}")
    return 124


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="JumpServer devops helper")
    p.add_argument("--base-url", default=os.getenv("JMS_BASE_URL", DEFAULT_BASE_URL), help="JumpServer base url")
    p.add_argument("--env-file", default=DEFAULT_ENV_FILE, help="env file path, default ~/.onesdev.env")
    p.add_argument("--access-key", default=os.getenv("JMS_ACCESS_KEY"), help="JMS access key")
    p.add_argument("--secret-key", default=os.getenv("JMS_SECRET_KEY"), help="JMS secret key")
    p.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds")

    sub = p.add_subparsers(dest="command_name", required=True)

    p_hosts = sub.add_parser("list-hosts", help="list accessible hosts")
    p_hosts.add_argument("--search")
    p_hosts.add_argument("--limit", type=int, default=20)
    p_hosts.add_argument("--offset", type=int, default=0)
    p_hosts.add_argument("--json", action="store_true")
    p_hosts.set_defaults(func=cmd_list_hosts)

    p_users = sub.add_parser("list-system-users", help="list system users for one host")
    p_users.add_argument("--asset-id", required=True)
    p_users.add_argument("--search")
    p_users.add_argument("--limit", type=int, default=20)
    p_users.add_argument("--offset", type=int, default=0)
    p_users.add_argument("--json", action="store_true")
    p_users.set_defaults(func=cmd_list_system_users)

    p_cmd = sub.add_parser("run-command", help="run shell command on one host")
    p_cmd.add_argument("--asset-id", required=True)
    p_cmd.add_argument("--system-user-id", required=True)
    p_cmd.add_argument("--command", required=True)
    p_cmd.add_argument("--poll-interval", type=float, default=2.0)
    p_cmd.add_argument("--timeout", type=int, default=120)
    p_cmd.add_argument("--json", action="store_true")
    p_cmd.set_defaults(func=cmd_run_command)

    p_params = sub.add_parser("ssh-params", help="get SSH connection parameters")
    p_params.add_argument("--asset-id", required=True)
    p_params.add_argument("--system-user-id", required=True)
    p_params.add_argument("--raw", action="store_true", help="show raw password")
    p_params.add_argument("--json", action="store_true")
    p_params.set_defaults(func=cmd_ssh_params)

    p_ssh = sub.add_parser("ssh-connect", help="connect to host via temporary SSH credential")
    p_ssh.add_argument("--asset-id", required=True)
    p_ssh.add_argument("--system-user-id", required=True)
    p_ssh.add_argument("--print-only", action="store_true", help="only print connection parameters")
    p_ssh.add_argument("--json", action="store_true")
    p_ssh.set_defaults(func=cmd_ssh_connect)
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    _load_env_file(args.env_file)
    access_key = args.access_key or os.getenv("JMS_ACCESS_KEY")
    secret_key = args.secret_key or os.getenv("JMS_SECRET_KEY")
    if not access_key or not secret_key:
        print(
            "Missing credentials. Set JMS_ACCESS_KEY and JMS_SECRET_KEY in environment or ~/.onesdev.env", file=sys.stderr
        )
        print(
            "Example ~/.onesdev.env:\n"
            "JMS_BASE_URL=https://devjumpserver.myones.net\n"
            "JMS_ACCESS_KEY=...\n"
            "JMS_SECRET_KEY=...",
            file=sys.stderr,
        )
        return 2

    base_url = os.getenv("JMS_BASE_URL", args.base_url)
    client = JumpServerClient(base_url=base_url, access_key=access_key, secret_key=secret_key, timeout=args.timeout)

    try:
        return args.func(client, args)
    except JmsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"ERROR: network request failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
