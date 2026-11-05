# Coding-agent settings and tool calling

[Documentation](../README.md) · [B200 installation](b200-slurm.md) · [RTX demo](../start/install.md)

Use this guide after the operator has started the service and supplied your gateway URL, model name and individual API key. Installing the service does not require an AI agent. OpenCode is an optional client that can read files, edit code and run commands on your own machine.

## 1. Understand the defaults

| Setting | Included configuration |
|---|---|
| Primary hardware | One B200 MIG `4g.90gb` allocation; GPU family detected automatically |
| Model | Qwen3.8-27B NVFP4, exposed as `qwen-coder` |
| Total context | 262,144 tokens, including input and generated output |
| Input target | 200,000 tokens, including history, tool definitions and tool results |
| Client output allowance | 32,768 tokens per response, including reasoning and final output |
| Thinking | Enabled, with `preserve_thinking: true` |
| Reasoning effort | `xhigh`; optional `medium` or `low` |
| Sampling | Temperature `1.0`, top-p `0.95`, top-k `20`, min-p `0.0` |
| Penalties | Presence `0.0`, repetition `1.0` |
| Active sequences / tensor parallel size | `1` / `1` |
| KV cache | FP8 E4M3 |
| Client request/header/stream-idle timeouts | 30 minutes, matching the gateway's request budget |

The thinking and sampling defaults follow the [official Qwen model card](https://huggingface.co/Qwen/Qwen3.8-27B#api-usage). The 32,768-token output allowance is this blueprint's practical starting point for a 262K service, also used in Qwen's reported QwenSWEBench evaluation. It is not a universal requirement or the model's maximum output length. A larger allowance consumes more of the same context window; it does not force long answers.

The [gateway configuration](../../gateway.yaml) supplies request defaults when a client omits those fields. Clients can override them. These settings are not enforced output caps. Other API clients should explicitly send `max_tokens: 32768` and reserve room for it in their input. The server's `MAX_NUM_BATCHED_TOKENS=8192` is a prefill scheduling setting, not the response limit; leave it unchanged.

## 2. Apply the configuration

For a new service, follow the [B200 installation guide](b200-slurm.md). It already uses these files. For an existing service, follow the [migration procedure](../operate/administration.md#migrate-an-existing-installation), reconcile any UI-stored model defaults, and restart the gateway with `docker compose restart gateway` on its host. Keep the existing secrets and database.

The launcher already includes `--reasoning-parser qwen3`, `--enable-auto-tool-choice` and `--tool-call-parser qwen3_coder`. These settings let vLLM turn Qwen's generated tool syntax into structured API tool calls. Restart the inference job only if its launch settings differ.

## 3. Connect OpenCode

Follow the [laptop setup commands](../start/install.md#optional-connect-opencode), using your operator's HTTPS URL ending in `/v1`, or the documented SSH tunnel. Copy [client/opencode.json](../../client/opencode.json) into your working directory as `opencode.json`; merge it into an existing configuration instead of replacing your settings.

The supplied configuration declares reasoning and tool-call capabilities and uses `interleaved.field: reasoning_content` to retain reasoning across tool-result turns. The default effort is `xhigh`; the supplied variants expose `low`, `medium` and `xhigh`, with unsupported `high` disabled. OpenCode executes its tools locally, subject to its permissions and the installed tool dependencies.

Provider timeouts are explicitly set to `1800000` milliseconds. OpenCode 1.19.5 otherwise uses five-minute header and stream-idle timeouts, which can abort a queued request or long prefill before the gateway's thirty-minute limit. The total request timeout still bounds each turn. These settings come from the versioned [provider fetch implementation](https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/provider/provider.ts).

The guides also set this environment variable before starting OpenCode:

```bash
export OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX=32768
```

OpenCode 1.19.5 otherwise applies an internal 32,000-token ceiling even when the model configuration allows 32,768. This environment variable raises that ceiling to match the supplied configuration. The behavior comes from the versioned [request preparation](https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/session/llm/request.ts), [runtime flags](https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/effect/runtime-flags.ts) and [provider transforms](https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/provider/transform.ts). Review these settings when changing client versions.

## 4. Use tools from your client

In OpenCode, use an agent mode with editing and command tools enabled. Start in a disposable project and ask it to read a file, make one small change and run the project's checks. Approve the requested operations according to your normal policy. The [step-by-step scratch exercise](b200-slurm.md#51-verify-opencode-on-an-ordinary-client) provides a complete example and expected results for use when a server is available.

For your own API client, implement the following loop using `/v1/chat/completions`:

1. Send conversation `messages`, JSON-schema function definitions in `tools`, `tool_choice: "auto"` and `max_tokens: 32768`. The gateway supplies the thinking and sampling defaults.
2. Receive the assistant message. Preserve its `content`, `reasoning_content` and complete `tool_calls` in conversation history. For streaming, assemble each call by its `index`, retain its ID and function name, and concatenate argument fragments before parsing JSON. Accumulate reasoning separately from answer text.
3. Validate each requested function and its arguments against your tool definitions, apply your client's permissions, and execute the allowed tool in your client environment. Neither the gateway nor vLLM executes your filesystem or shell tools.
4. Append one `role: "tool"` message for each call, with the matching `tool_call_id` and a string `content` containing its result or error. Return these after the assistant message, preserving all call/result IDs. Send the accumulated history and tool definitions again.
5. Repeat until the assistant produces a final answer without tool calls. Treat truncated output or incomplete argument JSON as an unsuccessful turn; never execute a partial call. Set a client-side turn limit for unattended loops.

Set `tool_choice: "none"` when a request must not invoke tools. Use a named function choice only when your application intentionally requires that function. Do not add a global `tool_choice` default to requests without tool definitions. If you explicitly send `chat_template_kwargs`, include both `enable_thinking: true` and `preserve_thinking: true`: gateway defaults fill missing top-level fields, not missing nested properties.

## When a tool call does not happen

| Symptom | What to check |
|---|---|
| The model describes an action but nothing runs | Your client must advertise and execute tools; a plain chat request does neither |
| Raw tool markup appears in text | Confirm the running vLLM process has the Qwen tool parser and automatic tool choice enabled |
| A later tool turn fails | Preserve assistant reasoning and match every tool result to its call ID |
| Streamed arguments are invalid JSON | Assemble all fragments for each call before parsing or executing |
| Editing or commands are denied | Check the client's agent mode, permissions, working directory and tool dependencies |
| Reasoning consumes the output allowance | Reduce effort to `medium`, narrow the task or increase the allowance within the total context limit |

## Validation status

These configuration changes were made without running tests, as requested, after the prototype server was retired. Earlier RTX reports cover the older settings. The existing `scripts/verify.py` intentionally uses a short, non-thinking diagnostic and one forced, non-streaming tool call; it does not establish that automatic or streamed thinking-mode tool calls work with the new defaults. Run deployment acceptance when a server is available before claiming end-to-end compatibility. Arbitrary client plugins, MCP tools and their external services need their own configuration and verification.
