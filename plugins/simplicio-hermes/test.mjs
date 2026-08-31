import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { test } from "node:test";
import { createHermesPlugin, HERMES_HOOKS, RUNTIME_MODE } from "./index.mjs";

function runtimeFixture() {
  const calls = { prepare: [], record: [] };
  const content = JSON.stringify({
    schema: "simplicio.mapper-prefix/v1",
    project_map: { files: Array(4000).fill("module_á.py") },
    symbol_index: { symbols: ["complete_map_tail"] },
  });
  return {
    calls, mcp_available: true, runtime_mode: RUNTIME_MODE,
    async prepare_model_call(input) {
      calls.prepare.push(input);
      return { status: "prepared", protected: true, api_request_id: input.api_request_id,
        provider_cache_status: "unknown", context_packet: {
          producer: "simplicio-native-mapper", complete_map_artifacts: true,
          content, bytes: Buffer.byteLength(content),
          content_sha256: createHash("sha256").update(content).digest("hex"),
        } };
    },
    async record_model_result(input) {
      calls.record.push(input);
      return { savings: { provider_cache_status: input.cache_read_input_tokens === undefined ? "unknown" : "reported" } };
    },
  };
}

test("registers only Mapper preparation and receipt surfaces", () => {
  assert.deepEqual(HERMES_HOOKS, ["on_session_start", "llm_request", "llm_execution", "post_api_request", "api_request_error"]);
  assert.equal(createHermesPlugin().mode, "mapper-only");
});

test("complete stable map reaches provider and keeps all native options", async () => {
  const runtime = runtimeFixture();
  const plugin = createHermesPlugin({ runtime });
  const request = {
    provider: "openrouter", model: "model",
    tools: [{ type: "function", name: "native_edit" }], stream: true,
    options: { temperature: 0.2, max_tokens: 300 },
    cache: { read: true, write: true },
    messages: [{ role: "user", content: "hello" }],
  };
  const original = structuredClone(request);
  const a = await plugin.hooks.llm_request({ ...request, api_request_id: "a", session_id: "s1" });
  const b = await plugin.hooks.llm_request({ ...request, api_request_id: "b", session_id: "s2" });
  assert.equal(a.messages[0].content, b.messages[0].content);
  assert.ok(Buffer.byteLength(a.messages[0].content) > 32768);
  assert.match(a.messages[0].content, /complete_map_tail/);
  assert.deepEqual(request, original);
  for (const field of ["provider", "model", "tools", "stream", "options", "cache"]) {
    assert.deepEqual(a[field], request[field]);
  }
  assert.deepEqual(a.messages.slice(1), request.messages);
  assert.equal(runtime.calls.prepare[0].protection_mode, "best_effort");
  assert.equal(runtime.calls.prepare[0].host_session_id, "s1");
  assert.equal(runtime.calls.prepare[0].messages, undefined);
  assert.equal(runtime.calls.prepare[0].tools, undefined);
  assert.equal(a.simplicio.provider_cache_status, "unknown");
});

for (const [field, value] of [
  ["system", "native policy"],
  ["system", [{ type: "text", text: "native policy", cache_control: { type: "ephemeral" } }]],
  ["instructions", "native policy"],
  ["input", [{ role: "user", content: "hello" }]],
  ["input", "hello"],
]) {
  test(`preserves ${field} provider shape and includes complete map`, async () => {
    const plugin = createHermesPlugin({ runtime: runtimeFixture() });
    const result = await plugin.prepare_model_call({ [field]: value });
    assert.match(JSON.stringify(result[field]), /complete_map_tail/);
    if (Array.isArray(value) && field === "system") assert.deepEqual(result[field][0], value[0]);
  });
}

test("unscoped full Runtime is never called", async () => {
  const runtime = runtimeFixture();
  runtime.runtime_mode = "full";
  const plugin = createHermesPlugin({ runtime });
  const original = { messages: [{ role: "user", content: "native work" }] };
  const result = await plugin.prepare_model_call(original);
  assert.deepEqual(result.messages, original.messages);
  assert.equal(runtime.calls.prepare.length, 0);
  assert.equal(result.simplicio.reason_code, "runtime_mapper_only_required");
});

test("legacy enforce settings migrate without blocking native requests", async () => {
  const runtime = runtimeFixture();
  runtime.prepare_model_call = async () => { throw new Error("secret-token"); };
  const plugin = createHermesPlugin({ runtime, mode: "enforce" });
  const request = { provider: "p", model: "m", tools: [{ name: "native" }], messages: [] };
  const result = await plugin.hooks.llm_request(request);
  assert.deepEqual(result.tools, request.tools);
  assert.equal(result.simplicio.protected, false);
  assert.equal(plugin.status().mode, "mapper-only");
  assert.doesNotMatch(JSON.stringify(plugin.status()), /secret-token/);
});

test("missing login and corrupt map never become provider context", async () => {
  for (const receipt of [
    { status: "login_required", login_required: true },
    { status: "degraded", protected: false },
    { status: "prepared", protected: true, context_packet: { content: "old full-mode handle" } },
  ]) {
    const runtime = runtimeFixture();
    runtime.prepare_model_call = async () => receipt;
    const result = await createHermesPlugin({ runtime }).prepare_model_call({ messages: [] });
    assert.deepEqual(result.messages, []);
    assert.equal(result.simplicio.protected, false);
  }
});

test("an explicit size budget omits the map without truncating or blocking", async () => {
  const plugin = createHermesPlugin({ runtime: runtimeFixture(), mode: "enforce", maxContextBytes: 64 });
  const result = await plugin.prepare_model_call({ messages: [] });
  assert.deepEqual(result.messages, []);
  assert.equal(result.simplicio.reason_code, "context_packet_too_large");
});

test("records actual cache telemetry with matching request and no source bodies", async () => {
  const runtime = runtimeFixture();
  const plugin = createHermesPlugin({ runtime });
  for (const id of ["a", "b"]) await plugin.prepare_model_call({
    messages: [], api_request_id: id, session_id: "s", turn_id: "t", provider: "p", model: "m",
  });
  await plugin.record_model_result({
    session_id: "s", api_request_id: "a", response: { id: "provider-a" },
    usage: { input_tokens: 20, prompt_tokens: 100, output_tokens: 4, cache_read_tokens: 80 },
  });
  const record = runtime.calls.record[0];
  assert.equal(record.api_request_id, "a");
  assert.equal(record.provider_request_id, "provider-a");
  assert.equal(record.cache_read_input_tokens, 80);
  assert.equal(record.input_tokens, 100);
  assert.doesNotMatch(JSON.stringify(record), /complete_map_tail/);
  assert.equal(plugin.status().provider_cache_status, "reported");
  await plugin.record_model_result({ session_id: "s", api_request_id: "b" });
  assert.equal(runtime.calls.record[1].cache_read_input_tokens, undefined);
  assert.equal(runtime.calls.record[1].provider_request_id, undefined);
  assert.equal(plugin.status().provider_cache_status, "unknown");
});

test("result recording failure never interrupts completed native work", async () => {
  const runtime = runtimeFixture();
  runtime.record_model_result = async () => { throw new Error("offline"); };
  const plugin = createHermesPlugin({ runtime, mode: "enforce" });
  await plugin.prepare_model_call({ messages: [], api_request_id: "a" });
  const event = { api_request_id: "a", result: { text: "native answer" } };
  const result = await plugin.record_model_result(event);
  assert.deepEqual(result.result, event.result);
  assert.equal(result.simplicio.reason_code, "runtime_record_failed");
});

test("execution is always the host's original event", () => {
  const event = { execute: () => "native" };
  assert.equal(createHermesPlugin().hooks.llm_execution(event), event);
});
