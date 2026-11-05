#!/usr/bin/env python3
"""Opt-in capacity probe: count using vLLM, then send a synthetic streamed request."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import time
import urllib.request


def post(url, key, body):
    return urllib.request.urlopen(urllib.request.Request(url,
        data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + key,
        "Content-Type": "application/json"}), timeout=1800)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:4001/v1")
    p.add_argument("--backend-url", default="http://127.0.0.1:8000")
    p.add_argument("--key-file", required=True, type=Path)
    p.add_argument("--backend-key-file", default=Path("runtime/secrets/backend.key"), type=Path)
    p.add_argument("--prompt-tokens", required=True, type=int)
    p.add_argument("--output-tokens", type=int, default=32768)
    p.add_argument("--context-limit", type=int, default=262144)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.prompt_tokens < 512 or a.output_tokens < 1 or a.prompt_tokens + a.output_tokens > a.context_limit:
        p.error("Require prompt >=512, output >=1 and prompt + output <= configured context limit")
    api_key, backend_key = a.key_file.read_text().strip(), a.backend_key_file.read_text().strip()
    needle = "PROBE_" + secrets.token_hex(8)
    line = "Archive entry: project utilities contain routine parsing and formatting helpers.\n"
    template_kwargs = {"enable_thinking": True, "preserve_thinking": True, "reasoning_effort": "xhigh"}

    def messages(repetitions):
        half = repetitions // 2
        content = ("Reference archive follows.\n" + line * half + "\nThe unique retrieval code is " + needle
            + ".\n" + line * (repetitions - half) + "\nReturn only the unique retrieval code from this archive.")
        return [{"role": "user", "content": content}]

    def count(repetitions):
        with post(a.backend_url.rstrip("/") + "/tokenize", backend_key, {
            "model": "qwen", "messages": messages(repetitions),
            "chat_template_kwargs": template_kwargs, "add_generation_prompt": True}) as response:
            return json.load(response)["count"]

    low, high = 0, max(1, a.prompt_tokens // 8)
    while count(high) < a.prompt_tokens:
        high *= 2
    while low < high:
        mid = (low + high) // 2
        if count(mid) < a.prompt_tokens:
            low = mid + 1
        else:
            high = mid
    measured = count(low)
    if measured + a.output_tokens > a.context_limit:
        p.error("Tokenized prompt plus output exceeds --context-limit; reduce target or output")
    started = time.monotonic()
    first_token = None
    text, usage = "", {}
    done = False
    finish_reason = None
    stream_error = False
    with post(a.base_url.rstrip("/") + "/chat/completions", api_key, {
        "model": "qwen-coder", "messages": messages(low),
        "chat_template_kwargs": template_kwargs,
        "reasoning_effort": "xhigh", "max_tokens": a.output_tokens,
        "stream": True, "stream_options": {"include_usage": True}}) as response:
        for raw in response:
            line_value = raw.decode().strip()
            if not line_value.startswith("data:"):
                continue
            data = line_value[5:].strip()
            if data == "[DONE]":
                done = True
                break
            event = json.loads(data)
            if event.get("error"):
                stream_error = True
                break
            if event.get("usage"):
                usage = event["usage"]
            for choice in event.get("choices", []):
                if choice.get("index", 0) != 0:
                    continue
                if choice.get("finish_reason") is not None:
                    finish_reason = choice["finish_reason"]
                content = choice.get("delta", {}).get("content") or ""
                if content and first_token is None:
                    first_token = time.monotonic() - started
                text += content
    result = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "synthetic_probe": True,
        "requested_prompt_tokens": a.prompt_tokens, "tokenizer_count": measured,
        "output_allowance": a.output_tokens, "context_limit": a.context_limit,
        "chat_template_kwargs": template_kwargs,
        "finish_reason": finish_reason, "stream_done": done, "stream_error": stream_error,
        "usage": usage, "time_to_first_content_seconds": first_token,
        "total_seconds": time.monotonic() - started, "needle_retrieved": needle in text,
        "passed": done and not stream_error and finish_reason == "stop"
        and usage.get("prompt_tokens", 0) >= a.prompt_tokens and needle in text}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
