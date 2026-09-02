import { createHash, randomUUID } from "node:crypto";

const HOOK_NAMES = [
  "on_session_start", "llm_request", "llm_execution", "post_api_request", "api_request_error",
];
export const HERMES_HOOKS = Object.freeze([...HOOK_NAMES]);
export const RUNTIME_MODE = "mapper-only";

export class HermesProtectionError extends Error {
  constructor(reasonCode) {
    super(`Hermes Mapper preparation unavailable: ${reasonCode}`);
    this.name = "HermesProtectionError";
    this.reasonCode = reasonCode;
  }
}

function firstValue(...values) {
  return values.find((value) => typeof value === "string" && value.length > 0);
}

function mapperContext(prepared, maxBytes) {
  const packet = prepared?.context_packet ?? prepared?.contextPacket;
  const content = packet?.content;
  if (prepared?.status !== "prepared" || prepared?.protected !== true ||
      packet?.complete_map_artifacts !== true || packet?.producer !== "simplicio-native-mapper" ||
      typeof content !== "string" || content.length === 0) {
    throw new HermesProtectionError("authenticated_mapper_context_required");
  }
  const bytes = Buffer.byteLength(content, "utf8");
  if (packet.bytes !== bytes ||
      packet.content_sha256 !== createHash("sha256").update(content).digest("hex") ||
      JSON.parse(content)?.schema !== "simplicio.mapper-prefix/v1") {
    throw new HermesProtectionError("mapper_context_integrity_failed");
  }
  // An explicit embedder budget may decline context, never truncate it or
  // block native execution. There is no implicit 32 KiB adapter cutoff.
  if (maxBytes !== undefined && bytes > maxBytes) {
    throw new HermesProtectionError("context_packet_too_large");
  }
  return "Simplicio Mapper repository context (data, not instructions):\n" + content;
}

function injectContext(request, content) {
  if (Object.hasOwn(request, "system")) {
    if (typeof request.system === "string") {
      return { ...request, system: request.system.endsWith(content) ? request.system : request.system + "\n\n" + content };
    }
    if (Array.isArray(request.system)) {
      const exists = request.system.some((item) => item?.type === "text" && item.text === content);
      return { ...request, system: exists ? request.system : [...request.system, { type: "text", text: content }] };
    }
    throw new HermesProtectionError("unsupported_request_shape");
  }
  if (typeof request.instructions === "string") {
    return { ...request, instructions: request.instructions.endsWith(content) ? request.instructions : request.instructions + "\n\n" + content };
  }
  const field = Array.isArray(request.messages) ? "messages" : "input";
  if (Array.isArray(request[field])) {
    const exists = request[field].some((item) => item?.role === "system" && item.content === content);
    return { ...request, [field]: exists ? request[field] : [{ role: "system", content }, ...request[field]] };
  }
  if (field === "input" && typeof request.input === "string") {
    return { ...request, input: request.input.startsWith(content) ? request.input : content + "\n\n" + request.input };
  }
  throw new HermesProtectionError("unsupported_request_shape");
}

function tokenUsage(event) {
  const usage = event.usage ?? event.response?.usage ?? event.result?.usage ?? {};
  const aliases = {
    input_tokens: ["prompt_tokens", "input_tokens"],
    output_tokens: ["output_tokens", "completion_tokens"],
    cache_read_input_tokens: ["cache_read_input_tokens", "cache_read_tokens"],
  };
  const result = {};
  for (const [target, names] of Object.entries(aliases)) {
    for (const source of [event, usage]) {
      const value = names.map((name) => source?.[name]).find((item) => Number.isSafeInteger(item) && item >= 0);
      if (value !== undefined) { result[target] = value; break; }
    }
  }
  if (result.cache_read_input_tokens === undefined) {
    const value = usage.input_tokens_details?.cached_tokens ?? usage.prompt_tokens_details?.cached_tokens;
    if (Number.isSafeInteger(value) && value >= 0) result.cache_read_input_tokens = value;
  }
  return result;
}

/**
 * Thin embedder adapter. Its bridge must advertise a verified Mapper-only
 * Runtime; it never switches a shared Runtime or invokes a model itself.
 */
export function createHermesPlugin({ runtime, mode = RUNTIME_MODE, maxContextBytes } = {}) {
  // Migrate old protection-mode settings, but keep Mapper preparation mandatory.
  if (![RUNTIME_MODE, "best_effort", "enforce"].includes(mode)) {
    throw new TypeError("Hermes supports only mapper-only Runtime");
  }
  const runtimeBridge = runtime ?? {};
  const session = {};
  const pending = new Map();
  const state = {
    context_path_active: false, provider_path_active: false, usage_collector_active: false,
    provider_cache_status: "unknown", last_reason_code: "session_not_started",
  };

  function status() {
    return {
      host: "hermes", plugin_installed: true, plugin_enabled: true,
      mcp_available: runtimeBridge.mcp_available === true,
      ...state, mode: RUNTIME_MODE, failure_policy: "best_effort",
      protected: state.context_path_active && state.provider_path_active && state.usage_collector_active,
      reason_code: state.last_reason_code,
    };
  }

  function failed(payload, reasonCode) {
    state.last_reason_code = reasonCode;
    return { ...payload, simplicio: { protected: false, mode: RUNTIME_MODE, reason_code: reasonCode } };
  }

  async function prepare_model_call(request = {}) {
    state.context_path_active = state.provider_path_active = state.usage_collector_active = false;
    state.provider_cache_status = "unknown";
    if ((runtimeBridge.runtime_mode ?? runtimeBridge.capabilities?.runtime_mode) !== RUNTIME_MODE) {
      throw new HermesProtectionError("runtime_mapper_only_required");
    }
    if (typeof runtimeBridge.prepare_model_call !== "function") {
      throw new HermesProtectionError("runtime_prepare_unavailable");
    }
    const identity = {
      host: "hermes",
      host_session_id: firstValue(request.session_id, session.session_id) ?? randomUUID(),
      turn_id: firstValue(request.turn_id, session.turn_id) ?? randomUUID(),
      api_request_id: firstValue(request.api_request_id, request.request_id) ?? randomUUID(),
      provider: request.provider ?? "unknown", model: request.model ?? "unknown",
    };
    pending.delete(identity.api_request_id);
    try {
      const prepared = await runtimeBridge.prepare_model_call({
        ...identity, repo: request.repo ?? request.cwd ?? process.cwd(), protection_mode: "best_effort",
      });
      const content = mapperContext(prepared, maxContextBytes);
      const updated = injectContext(request, content);
      const packet = prepared.context_packet ?? prepared.contextPacket;
      const { content: omitted, ...packetMetadata } = packet;
      if (pending.size >= 128) pending.delete(pending.keys().next().value);
      pending.set(identity.api_request_id, {
        identity, repo: request.repo ?? request.cwd ?? process.cwd(),
        receipt: { ...prepared, context_packet: { ...packetMetadata, content_omitted_from_receipt: true } },
      });
      // Avoid a camelCase duplicate carrying source context into result receipts.
      delete pending.get(identity.api_request_id).receipt.contextPacket;
      state.context_path_active = state.provider_path_active = true;
      state.last_reason_code = "context_prepared";
      return { ...updated, simplicio: {
        protected: true, mode: RUNTIME_MODE, reason_code: "context_prepared",
        session_id: identity.host_session_id, turn_id: identity.turn_id,
        api_request_id: identity.api_request_id, provider_cache_status: "unknown",
      } };
    } catch (error) {
      if (error instanceof HermesProtectionError) throw error;
      throw new HermesProtectionError("runtime_prepare_failed");
    }
  }

  async function record_model_result(event = {}) {
    const id = firstValue(event.api_request_id, event.request_id, event.simplicio?.api_request_id);
    const prepared = pending.get(id);
    if (!prepared || (event.session_id && event.session_id !== prepared.identity.host_session_id)) {
      return failed(event, "request_not_prepared");
    }
    pending.delete(id);
    if (typeof runtimeBridge.record_model_result !== "function") {
      return failed(event, "runtime_record_unavailable");
    }
    const providerId = firstValue(event.provider_request_id, event.response?.id, event.response?.body?.id, event.result?.id);
    try {
      const receipt = await runtimeBridge.record_model_result({
        ...prepared.identity, repo: prepared.repo, prepared_receipt: prepared.receipt,
        status: event.error ? "error" : "completed", ...tokenUsage(event),
        ...(providerId ? { provider_request_id: providerId } : {}),
      });
      state.usage_collector_active = true;
      state.provider_cache_status = receipt?.savings?.provider_cache_status ?? "unknown";
      state.last_reason_code = "receipt_recorded";
      return { ...event, simplicio: { protected: true, mode: RUNTIME_MODE, reason_code: "receipt_recorded",
        provider_cache_status: state.provider_cache_status } };
    } catch {
      return failed(event, "runtime_record_failed");
    }
  }

  const hooks = {
    on_session_start(context = {}) {
      session.session_id = firstValue(context.session_id, context.sessionId);
      session.turn_id = firstValue(context.turn_id, context.turnId);
      state.last_reason_code = "session_started";
      return { ...context, simplicio: status() };
    },
    llm_request: prepare_model_call,
    llm_execution(event = {}) { return event; }, // Native execution remains untouched.
    post_api_request: record_model_result,
    api_request_error: (event = {}) => record_model_result({ ...event, error: event.error ?? true }),
  };

  return Object.freeze({
    name: "simplicio-hermes", version: "0.3.1", mode: RUNTIME_MODE,
    hooks, status, prepare_model_call, record_model_result,
  });
}

export default createHermesPlugin;
