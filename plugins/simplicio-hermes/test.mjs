import assert from "node:assert/strict";
import { test } from "node:test";
import { createHermesPlugin, HermesProtectionError, HERMES_HOOKS } from "./index.mjs";

function runtimeFixture() {
  const calls = { prepare: [], record: [] };
  return {
    calls,
    mcp_available: true,
    async prepare_model_call(input) {
      calls.prepare.push(input);
      return { contextPacket: { generation: "g1", facts: ["bounded"] }, generation: "g1" };
    },
    async record_model_result(input) {
      calls.record.push(input);
    },
  };
}

test("registers every native request/receipt surface", () => {
  assert.deepEqual(HERMES_HOOKS, ["on_session_start", "llm_request", "llm_execution", "post_api_request", "api_request_error"]);
});

test("prepares every provider request and preserves provider identity/options", async () => {
  const runtime = runtimeFixture();
  const plugin = createHermesPlugin({ runtime, mode: "enforce" });
  plugin.hooks.on_session_start({ session_id: "s1", turn_id: "t1" });
  const request = {
    provider: "openrouter",
    model: "anthropic/claude-sonnet",
    tools: [{ type: "function", name: "search" }],
    stream: true,
    options: { temperature: 0.2, max_tokens: 300 },
    cache: { read: true, write: true },
    messages: [{ role: "user", content: "hello" }],
  };
  const prepared = await plugin.hooks.llm_request(request);
  assert.equal(prepared.provider, request.provider);
  assert.equal(prepared.model, request.model);
  assert.deepEqual(prepared.tools, request.tools);
  assert.deepEqual(prepared.options, request.options);
  assert.deepEqual(prepared.cache, request.cache);
  assert.equal(prepared.messages[1].content, "hello");
  assert.match(prepared.messages[0].content, /bounded/);
  assert.deepEqual(runtime.calls.prepare[0], {
    provider: request.provider,
    model: request.model,
    tools: request.tools,
    stream: true,
    streaming: undefined,
    options: request.options,
    cache: request.cache,
    cache_control: undefined,
    provider_options: undefined,
    host: "hermes",
    session_id: "s1",
    turn_id: "t1",
    api_request_id: undefined,
    provider_request_id: undefined,
    host_session_id: "s1",
    host_turn_id: "t1",
  });
  assert.equal(plugin.status().protected, false);
});

test("records usage/cache/cost and correlates all request identifiers", async () => {
  const runtime = runtimeFixture();
  const plugin = createHermesPlugin({ runtime, mode: "best_effort" });
  plugin.hooks.on_session_start({ session_id: "s1" });
  await plugin.hooks.llm_request({ provider: "openai", model: "gpt-5", messages: [] });
  const execution = plugin.hooks.llm_execution({ turn_id: "t2", api_request_id: "a2", provider_request_id: "p2" });
  assert.equal(execution.simplicio.api_request_id, "a2");
  await plugin.hooks.post_api_request({
    session_id: "s1",
    turn_id: "t2",
    api_request_id: "a2",
    provider_request_id: "p2",
    usage: { input_tokens: 10, output_tokens: 4 },
    cache: { read_tokens: 8, write_tokens: 2 },
    cost: { usd: 0.01 },
  });
  assert.deepEqual(runtime.calls.record[0].usage, { input_tokens: 10, output_tokens: 4 });
  assert.deepEqual(runtime.calls.record[0].cache, { read_tokens: 8, write_tokens: 2 });
  assert.equal(runtime.calls.record[0].provider_request_id, "p2");
  assert.equal(runtime.calls.record[0].api_request_id, "a2");
  assert.equal(plugin.status().usage_collector_active, true);
});

test("enforce blocks a provider request when preparation fails", async () => {
  const plugin = createHermesPlugin({
    runtime: { async prepare_model_call() { throw new Error("offline"); } },
    mode: "enforce",
  });
  await assert.rejects(
    plugin.hooks.llm_request({ provider: "x", model: "y", messages: [] }),
    (error) => error instanceof HermesProtectionError && error.reasonCode === "runtime_prepare_failed",
  );
  assert.equal(plugin.status().protected, false);
});

test("best_effort remains fail-open but exposes typed protection status", async () => {
  let llmCalls = 0;
  const plugin = createHermesPlugin({
    runtime: { async prepare_model_call() { throw new Error("offline"); } },
    mode: "best_effort",
  });
  const request = { provider: "x", model: "y", tools: [{ name: "keep" }], messages: [] };
  const result = await plugin.hooks.llm_request(request);
  llmCalls += 1;
  assert.equal(llmCalls, 1);
  assert.equal(result.provider, request.provider);
  assert.equal(result.model, request.model);
  assert.deepEqual(result.tools, request.tools);
  assert.equal(result.simplicio.protected, false);
  assert.equal(plugin.status().reason_code, "runtime_prepare_failed");
  assert.doesNotMatch(JSON.stringify(plugin.status()), /offline|secret|hello/);
});
