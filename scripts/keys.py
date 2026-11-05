#!/usr/bin/env python3
"""Use agentgateway's native resource API; credentials stay in private files."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class Admin:
    def __init__(self, credentials=None):
        c = credentials or json.loads((ROOT / "runtime/secrets/admin.json").read_text())
        self.url = c["url"].rstrip("/")
        self.authorization = "Basic " + base64.b64encode(
            (c["username"] + ":" + c["password"]).encode()).decode()

    def request(self, method, path, value=None):
        request = urllib.request.Request(self.url + path, method=method,
            data=None if value is None else json.dumps(value).encode(),
            headers={"Authorization": self.authorization, "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else {}

    def create(self, name, models=None, daily_tokens=None):
        token = "agw_sk_" + secrets.token_urlsafe(32)
        value = {"keyHash": "sha256:" + hashlib.sha256(token.encode()).hexdigest(),
                 "metadata": {"name": name, "user": name},
                 "allowedModels": models if models is not None else ["qwen-coder"]}
        if daily_tokens:
            value["budgets"] = [{"name": "daily-tokens", "limit": {"unit": "Tokens", "amount": daily_tokens},
                "window": {"rolling": "24h"}, "onBudgetExceeded": "Block"}]
        response = self.request("PUT", "/api/config/resources/llm.apiKey", {"resources": [{"value": value}]})
        return token, response

    def list(self):
        return self.request("GET", "/api/config/resources/llm.apiKey")

    def revoke(self, resource_id):
        return self.request("DELETE", "/api/config/resources/llm.apiKey/" + urllib.parse.quote(resource_id, safe=""))


def key_summary(response):
    resources = []
    for resource in response.get("resources", []):
        value = resource.get("value", {})
        metadata = value.get("metadata", {})
        resources.append({"id": resource["id"], "name": metadata.get("name"),
            "user": metadata.get("user"), "allowedModels": value.get("allowedModels"),
            "budgets": value.get("budgets", []),
            "storage": "raw" if value.get("key") else "hashed" if value.get("keyHash") else "unknown"})
    return {"resources": resources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    create.add_argument("name")
    create.add_argument("--out", required=True, type=Path)
    create.add_argument("--daily-tokens", type=int)
    sub.add_parser("list")
    revoke = sub.add_parser("revoke")
    revoke.add_argument("id")
    args = parser.parse_args()
    admin = Admin()
    if args.action == "create":
        if args.daily_tokens is not None and args.daily_tokens <= 0:
            parser.error("--daily-tokens must be positive")
        if args.out.exists():
            parser.error("Output exists; choose a new private file")
        os.umask(0o077)
        # Reserve output before creating a remotely persisted credential.
        with args.out.open("x") as out:
            os.chmod(args.out, 0o600)
            token, response = admin.create(args.name, daily_tokens=args.daily_tokens)
            out.write(token + "\n")
        print(f"Created key for {args.name}; secret saved only to {args.out}")
        print(json.dumps(key_summary(response), indent=2))
    elif args.action == "list":
        print(json.dumps(key_summary(admin.list()), indent=2))
    else:
        print(json.dumps(admin.revoke(args.id), indent=2))


if __name__ == "__main__":
    main()
