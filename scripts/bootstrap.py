#!/usr/bin/env python3
"""Initialize private runtime files; never print credentials or overwrite them."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def validate_url(value):
    url = urlsplit(value)
    if (url.scheme not in ("http", "https") or not url.hostname or url.username
            or url.password or url.query or url.fragment or url.path.rstrip("/") != "/v1"
            or any(c.isspace() or c in '$\"\'`' for c in value)):
        raise ValueError("Use an HTTP(S) base URL ending in /v1, without credentials or query")
    return value.rstrip("/")


def write_private(path, value):
    with path.open("x", encoding="utf-8") as out:
        os.chmod(path, 0o600)
        out.write(value)


def password_hash(password):
    try:
        import bcrypt
        return "admin:" + bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() + "\n"
    except ImportError:
        if not shutil.which("htpasswd"):
            raise RuntimeError("Install apache2-utils (htpasswd), or provide Python bcrypt")
        return subprocess.check_output(
            ["htpasswd", "-niB", "admin"], input=password + "\n", text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-key-file", required=True, type=Path)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000/v1", type=validate_url)
    args = parser.parse_args()
    backend_key = args.backend_key_file.read_text().strip()
    if not backend_key or any(c.isspace() for c in backend_key):
        parser.error("Backend key must be one non-empty token")
    if (ROOT / ".env").exists() or (ROOT / "runtime/secrets/admin.json").exists():
        parser.error("Already initialized; existing credentials preserved. See docs/operate/administration.md")
    password = secrets.token_urlsafe(32)
    hashed = password_hash(password)
    os.umask(0o077)
    for name in ("runtime/secrets", "runtime/data"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
        (ROOT / name).chmod(0o700)
    write_private(ROOT / "runtime/secrets/backend.key", backend_key + "\n")
    write_private(ROOT / "runtime/secrets/admin.htpasswd", hashed)
    write_private(ROOT / "runtime/secrets/admin.json", json.dumps({
        "username": "admin", "password": password, "url": "http://127.0.0.1:14002"
    }) + "\n")
    write_private(ROOT / ".env", f"GATEWAY_UID={os.getuid()}\nGATEWAY_GID={os.getgid()}\n"
                  f"VLLM_BASE_URL={args.backend_url}\n")
    print("Initialized. Admin credentials: runtime/secrets/admin.json (private).")
    print("Validate: docker compose run --rm gateway --validate-only -f /config/gateway.yaml")
    print("Start: docker compose up -d")


if __name__ == "__main__":
    main()
