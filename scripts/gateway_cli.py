#!/usr/bin/env python3
"""Manage this blueprint's gateway from one command. GPU jobs remain separate."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from backup import backup
from keys import Admin, ROOT, key_summary


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def table(headers, rows):
    def cell(value):
        return "".join(c if c.isprintable() else " " for c in str(value))[:100]
    lines = [list(map(cell, headers)), *[list(map(cell, row)) for row in rows]]
    widths = [max(len(row[i]) for row in lines) for i in range(len(headers))]
    for row in lines:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths)).rstrip())


def compose(*arguments):
    if sys.platform != "linux":
        raise ValueError("Run service commands on the Linux gateway host. This blueprint uses Linux host networking.")
    if not (ROOT / ".env").is_file():
        raise ValueError("Gateway is not initialized. Follow docs/start/install.md or docs/deploy/b200-slurm.md.")
    if not shutil.which("docker"):
        raise ValueError("Docker is missing. Run ./gateway prerequisites --install on the Ubuntu gateway host.")
    if os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_CONTEXT"):
        raise ValueError("Use a local Docker context on the gateway host; unset DOCKER_HOST and DOCKER_CONTEXT first.")
    command = ["docker", "--context", "default", "compose", "--project-name", "qwen-agentgateway",
               "--project-directory", str(ROOT), "--env-file", str(ROOT / ".env"),
               "-f", str(ROOT / "compose.yaml"), *arguments]
    return subprocess.run(command, cwd=ROOT, check=True)


def status():
    compose("ps", "--all", "gateway")
    try:
        with urllib.request.urlopen("http://127.0.0.1:15022/healthz/ready", timeout=5) as response:
            ready = response.status == 200
    except (urllib.error.URLError, OSError):
        ready = False
    print("Gateway readiness: " + ("ready" if ready else "not ready"))
    print("Model/GPU job: managed separately; gateway readiness does not confirm model availability.")
    return 0 if ready else 1


def users(args):
    if not (ROOT / "runtime/secrets/admin.json").is_file():
        raise ValueError("Administrator credentials are missing. Complete gateway bootstrap in the installation guide first.")
    admin = Admin()
    if args.action == "add":
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", args.name):
            raise ValueError("Use a name of 1–64 letters, digits, dots, underscores or hyphens, starting with a letter/digit.")
        path = args.out.expanduser().resolve() if args.out else ROOT / "runtime/secrets" / (args.name + ".key")
        if not path.parent.is_dir():
            raise ValueError("Key output directory does not exist. Create a private directory or use the default path.")
        # The existing helper handles exclusive creation, hashing and private permissions.
        command = [sys.executable, str(ROOT / "scripts/keys.py"), "create", args.name, "--out", str(path)]
        if not args.unlimited:
            command += ["--daily-tokens", str(args.daily_tokens)]
        subprocess.run(command, cwd=ROOT, check=True)
        print("Allow a short interval for activation. Transfer the key using your approved secret channel.")
        return
    if args.action == "revoke":
        admin.revoke(args.id)
        print("Key revoked. Allow a short interval for reload; in-flight requests can still finish.")
        print("The local key file, if any, is retained. Remove unnecessary copies through your normal secret handling.")
        return
    resources = key_summary(admin.list())["resources"]
    if args.json:
        print(json.dumps({"resources": resources}, indent=2))
        return
    if not resources:
        print("No user keys. Create one with ./gateway users add NAME --daily-tokens 1000000")
        return
    rows = []
    for resource in resources:
        budgets = "; ".join(
            f'{b.get("limit", {}).get("amount", "?")} {b.get("limit", {}).get("unit", "?")}'
            f'/{b.get("window", {}).get("rolling", "custom window")}' for b in (resource["budgets"] or [])) or "none"
        rows.append([resource["id"], resource["name"] or "—", ", ".join(resource["allowedModels"] or []), budgets])
    table(["KEY ID", "NAME", "MODELS", "BUDGETS"], rows)
    print("Use the KEY ID to revoke. Names can have multiple keys. Use --json for complete budget details.")


def usage(args):
    path = ROOT / "runtime/data/agentgateway.db"
    if not path.is_file():
        raise ValueError("No gateway database yet. Start the initialized gateway and send a request first.")
    start = None if args.all else datetime.now(timezone.utc) - timedelta(days=args.days)
    clauses, parameters = [], []
    if start:
        clauses.append("julianday(completed_at) >= julianday(?)")
        parameters.append(start.isoformat())
    if args.user:
        clauses.append("agentgateway_user = ?")
        parameters.append(args.user)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    query = """SELECT agentgateway_user AS user, COUNT(*) AS requests,
        COALESCE(SUM(input_tokens), 0) AS input_tokens,
        COALESCE(SUM(output_tokens), 0) AS output_tokens,
        SUM(CASE WHEN input_tokens IS NULL OR output_tokens IS NULL THEN 1 ELSE 0 END) AS missing_usage,
        SUM(CASE WHEN http_status >= 400 OR error IS NOT NULL THEN 1 ELSE 0 END) AS errors
        FROM request_logs""" + where + " GROUP BY agentgateway_user ORDER BY input_tokens + output_tokens DESC"
    db = sqlite3.connect("file:" + urllib.parse.quote(str(path)) + "?mode=ro", uri=True, timeout=5)
    try:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute(query, parameters)]
    finally:
        db.close()
    if args.json:
        print(json.dumps({"from_utc": start.isoformat() if start else None, "users": rows}, indent=2))
        return
    print("Recorded usage: " + ("all retained history" if start is None else "since " + start.isoformat()))
    if rows:
        table(["USER", "REQUESTS", "INPUT", "OUTPUT", "MISSING USAGE", "ERRORS"],
              [[row["user"] if row["user"] is not None else "(unattributed)", row["requests"],
                f'{row["input_tokens"]:,}', f'{row["output_tokens"]:,}', row["missing_usage"], row["errors"]] for row in rows])
    else:
        print("No recorded requests in this window.")
    print("Completed, persisted requests only; totals can lag. This is not a remaining-budget or billing report.")


def snapshot(args):
    if args.out:
        destination = args.out.expanduser().resolve()
    else:
        folder = ROOT / "runtime/backups"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        destination = folder / ("agentgateway-" + stamp + ".db")
    backup(ROOT / "runtime/data/agentgateway.db", destination)
    print("Consistent SQLite snapshot saved: " + str(destination))
    print("Database only. Back up configuration and secrets separately using your encrypted off-host process.")


def main():
    parser = argparse.ArgumentParser(prog="./gateway", description=__doc__,
        epilog="Run on the gateway host. For packages: ./gateway prerequisites --help. No command starts a GPU job.")
    sub = parser.add_subparsers(dest="command")
    for name, help_text in [("start", "Create/start the gateway container"), ("stop", "Stop the gateway, preserving data"),
                            ("restart", "Restart the gateway"), ("status", "Show container status and readiness")]:
        sub.add_parser(name, help=help_text)
    logs = sub.add_parser("logs", help="Show gateway logs")
    logs.add_argument("--follow", "-f", action="store_true")
    logs.add_argument("--tail", type=positive, default=100)
    user = sub.add_parser("users", help="Manage model-scoped API keys")
    actions = user.add_subparsers(dest="action", required=True)
    add = actions.add_parser("add", help="Create a user key; save the secret to a private file")
    add.add_argument("name")
    budget = add.add_mutually_exclusive_group(required=True)
    budget.add_argument("--daily-tokens", type=positive)
    budget.add_argument("--unlimited", action="store_true", help="Explicitly create a key without a token budget")
    add.add_argument("--out", type=Path, help="Private key file; default: runtime/secrets/NAME.key")
    listing = actions.add_parser("list", help="List key metadata without exposing secrets")
    listing.add_argument("--json", action="store_true")
    revoke = actions.add_parser("revoke", help="Revoke the key ID from users list")
    revoke.add_argument("id")
    report = sub.add_parser("usage", help="Show recorded per-user token totals from local SQLite")
    period = report.add_mutually_exclusive_group()
    period.add_argument("--days", type=positive, default=1, help="Last N days; default: 1 (rolling 24 hours)")
    period.add_argument("--all", action="store_true", help="All retained history")
    report.add_argument("--user", help="Exact user identity filter")
    report.add_argument("--json", action="store_true")
    archive = sub.add_parser("backup", help="Take a private, consistent database snapshot")
    archive.add_argument("--out", type=Path, help="New output file; default: runtime/backups/TIMESTAMP.db")
    sub.add_parser("prerequisites", help="Check/install host packages; handled by the shell launcher")
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "prerequisites":
        return subprocess.run(["bash", str(ROOT / "scripts/prerequisites.sh")], cwd=ROOT).returncode
    if args.command == "status":
        return status()
    if args.command in ("start", "stop", "restart"):
        operations = {"start": ["up", "-d", "gateway"], "stop": ["stop", "gateway"], "restart": ["restart", "gateway"]}
        compose(*operations[args.command])
        print("Gateway command completed. GPU jobs and persistent data are unchanged.")
    elif args.command == "logs":
        compose("logs", "--tail", str(args.tail), *(["--follow"] if args.follow else []), "gateway")
    elif args.command == "users":
        users(args)
    elif args.command == "usage":
        usage(args)
    elif args.command == "backup":
        snapshot(args)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except subprocess.CalledProcessError as exc:
        print(f"Command failed (exit {exc.returncode}); see the output above.", file=sys.stderr)
        sys.exit(exc.returncode if exc.returncode > 0 else 1)
    except urllib.error.HTTPError as exc:
        print(f"Gateway administration returned HTTP {exc.code}. Check ./gateway status and the administrator credentials.", file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, OverflowError, sqlite3.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
