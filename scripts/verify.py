#!/usr/bin/env python3
"""Exercise an isolated running gateway; creates and revokes temporary keys."""
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

from keys import Admin, ROOT


def call(base, path, token=None, body=None, authorization=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if authorization:
        headers["Authorization"] = authorization
    request = urllib.request.Request(base + path, headers=headers,
        data=None if body is None else json.dumps(body).encode())
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read().decode()
            return response.status, data, round(time.monotonic() - started, 3)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(), round(time.monotonic() - started, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4001")
    parser.add_argument("--out", type=Path, default=ROOT / "runtime/gateway-acceptance.json")
    parser.add_argument("--restart", action="store_true", help="Restart ONLY this package's Compose gateway")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    admin = Admin()
    run = "acceptance-" + uuid.uuid4().hex[:10]
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "run": run,
              "hardware_scope": "Backend hardware must be recorded separately", "checks": {}}
    created = []

    def check(name, condition, details=None):
        report["checks"][name] = {"passed": bool(condition), "details": details}
        if not condition:
            raise AssertionError(name)

    def create(suffix, models=None, budget=None):
        token, result = admin.create(run + suffix, models, budget)
        key_id = result["resources"][0]["id"]
        created.append(key_id)
        # Resource writes are persisted before the serving configuration reload completes.
        for attempt in range(40):
            status, _, _ = call(base, "/v1/models", token)
            if status == 200:
                break
            time.sleep(0.25)
        check("key_activation" + suffix, status == 200)
        return token, key_id

    body = {"model": "qwen-coder", "messages": [{"role": "user", "content": "Say GATEWAY_OK."}],
            "temperature": 0, "max_tokens": 64, "chat_template_kwargs": {"enable_thinking": False}}
    try:
        for name, token in (("missing_key_rejected", None), ("invalid_key_rejected", "invalid-test-key")):
            status, _, _ = call(base, "/v1/chat/completions", token, body)
            check(name, status == 401, {"status": status})
        status, _, _ = call(admin.url, "/api/runtime")
        check("admin_auth_required", status == 401, {"status": status})
        runtime = admin.request("GET", "/api/runtime")
        check("hybrid_storage", runtime.get("ui", {}).get("configStoreMode") == "hybrid")
        status, html, _ = call(admin.url, "/ui/llm/keys", authorization=admin.authorization)
        check("protected_ui_served", status == 200 and "<html" in html.lower())
        token, key_id = create("-user")
        status, data, _ = call(base, "/v1/models", token)
        check("model_list", status == 200 and "qwen-coder" in data)
        status, _, _ = call(admin.url, "/api/config/resources/llm.apiKey", token)
        check("user_cannot_administer", status in (401, 403), {"status": status})
        status, _, _ = call(base, "/api/config/resources/llm.apiKey", token)
        check("no_admin_on_model_listener", status in (400, 401, 403, 404, 405), {"status": status})
        denied, _ = create("-restricted", ["another-model"])
        status, _, _ = call(base, "/v1/chat/completions", denied, body)
        check("model_scope_enforced", status == 403, {"status": status})
        canary = "PROMPT_CANARY_" + uuid.uuid4().hex
        chat = dict(body, messages=[{"role": "user", "content": "Say GATEWAY_OK. Ignore this marker: " + canary}])
        status, data, elapsed = call(base, "/v1/chat/completions", token, chat)
        result = json.loads(data)
        check("chat_and_usage", status == 200 and result.get("usage", {}).get("total_tokens", 0) > 0,
              {"status": status, "seconds": elapsed, "usage": result.get("usage")})
        status, data, _ = call(base, "/v1/chat/completions", token,
            dict(body, stream=True, stream_options={"include_usage": True}))
        events = [json.loads(line[6:]) for line in data.splitlines()
                  if line.startswith("data: ") and line[6:] != "[DONE]"]
        usage = next((event["usage"] for event in events if event.get("usage")), {})
        check("streaming_and_usage", status == 200 and "[DONE]" in data and usage.get("total_tokens", 0) > 0,
              {"usage": usage})
        tool = {"type": "function", "function": {"name": "read_file", "description": "Read a text file",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}
        messages = [{"role": "user", "content": "Read demo.py using read_file, then report the number returned."}]
        status, data, _ = call(base, "/v1/chat/completions", token, dict(body, messages=messages,
            tools=[tool], tool_choice={"type": "function", "function": {"name": "read_file"}}, max_tokens=256))
        result = json.loads(data)
        message = result["choices"][0]["message"]
        calls = message.get("tool_calls", [])
        check("tool_call", status == 200 and len(calls) == 1 and calls[0]["function"]["name"] == "read_file")
        check("tool_arguments", json.loads(calls[0]["function"]["arguments"]).get("path") == "demo.py")
        messages += [message, {"role": "tool", "tool_call_id": calls[0]["id"], "content": "The file contains: answer = 42"}]
        status, data, _ = call(base, "/v1/chat/completions", token, dict(body, messages=messages, tools=[tool], tool_choice="none"))
        check("tool_result_round_trip", status == 200 and "42" in json.loads(data)["choices"][0]["message"].get("content", ""))
        budget_token, _ = create("-budget", budget=1)
        status, _, _ = call(base, "/v1/chat/completions", budget_token, body)
        check("budget_initial_request", status == 200)
        time.sleep(1)
        status, _, _ = call(base, "/v1/chat/completions", budget_token, body)
        check("token_budget_blocks_later_request", status == 429, {"status": status})
        if args.restart:
            subprocess.run(["docker", "compose", "restart", "gateway"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
            for attempt in range(30):
                try:
                    status, _, _ = call(base, "/v1/models", token)
                    if status == 200:
                        break
                except OSError:
                    pass
                time.sleep(1)
            check("key_survives_restart", status == 200)
            status, _, _ = call(base, "/v1/chat/completions", budget_token, body)
            check("budget_survives_restart", status == 429)
        else:
            report["restart_test"] = "Not requested; run with --restart on isolated prototype"
        admin.revoke(key_id)
        created.remove(key_id)
        for attempt in range(40):
            status, _, _ = call(base, "/v1/models", token)
            if status == 401:
                break
            time.sleep(0.25)
        check("revocation", status == 401)
        db_path = ROOT / "runtime/data/agentgateway.db"
        db = sqlite3.connect("file:" + urllib.parse.quote(str(db_path)) + "?mode=ro", uri=True)
        check("sqlite_integrity", db.execute("PRAGMA quick_check").fetchone()[0] == "ok")
        for attempt in range(20):
            row = db.execute("SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens) FROM request_logs WHERE agentgateway_user=?", (run + "-user",)).fetchone()
            if row[0] >= 4 and row[1] and row[2]:
                break
            time.sleep(0.5)
        check("durable_per_user_usage", row[0] >= 4 and row[1] > 0 and row[2] > 0,
              {"requests": row[0], "input_tokens": row[1], "output_tokens": row[2]})
        payloads = db.execute("SELECT COUNT(*) FROM request_log_payloads WHERE request_prompt_json IS NOT NULL OR response_completion_json IS NOT NULL").fetchone()[0]
        check("no_prompt_response_payloads", payloads == 0, {"payload_rows": payloads})
        # Only synthetic canary presence is exported, never database contents.
        check("no_prompt_in_log_attributes", db.execute("SELECT COUNT(*) FROM request_logs WHERE attributes_json LIKE ?", ("%" + canary + "%",)).fetchone()[0] == 0)
        db.close()
    except Exception as exc:
        report["failure"] = type(exc).__name__ + ": " + str(exc)
    finally:
        for resource_id in created:
            try:
                admin.revoke(resource_id)
            except Exception:
                report.setdefault("cleanup_failures", []).append(resource_id)
        report["passed"] = "failure" not in report and "cleanup_failures" not in report
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
