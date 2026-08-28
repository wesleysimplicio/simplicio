const HOOK_NAMES = [
  "on_session_start",
  "llm_request",
  "llm_execution",
  "post_api_request",
  "api_request_error",
];

const DEFAULT_MAX_CONTEXT_BYTES = 32 * 1024;

export const HERMES_HOOKS = Object.freeze([...HOOK_NAMES]);

export class HermesProtectionError extends Error {
  constructor(reasonCode, cause) {
    super(`Hermes protection blocked the provider request: ${reasonCode}`);
    this.name = "HermesProtectionError";
    this.reasonCode = reasonCode;
    this.cause = cause;
  }
}

function stringValue(value) {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function firstValue(...values) {
  return values.map(stringValue).find(Boolean);
}

function byteLength(value) {
  return new TextEncoder().encode(value).byteLength;
}

function boundedPacket(packet, maxBytes) {
  const serialized = typeof packet === "string" ? packet : JSON.stringify(packet);
  if (!serialized || byteLength(serialized) > maxBytes) {
    throw new HermesProtectionError("context_packet_too_large");
  }
  return serialized;
}

function summarizeError(error) {
  return {
    name: error instanceof Error ? error.name : "Error",
    message: error instanceof Error ? error.message.slice(0, 160) : "Runtime error",
  };
}

function requestIdentity(request, session) {
  return {
    host: "hermes",
    session_id: firstValue(request.session_id, session.session_id),
    turn_id: firstValue(request.turn_id, session.turn_id),
    api_request_id: firstValue(request.api_request_id, request.request_id),
    provider_request_id: firstValue(request.provider_request_id),
    provider: request.provider,
    model: request.model,
  };
}

function selectedRequest(request) {
  // These fields are passed through unchanged to the Runtime and are never
  // replaced by the adapter. Messages/input are deliberately excluded here.
  return {
    provider: request.provider,
    model: request.model,
    tools: request.tools,
    stream: request.stream,
    streaming: request.streaming,
    options: request.options,
    cache: request.cache,
    cache_control: request.cache_control,
    provider_options: request.provider_options,
  };
}

function injectContext(request, contextPacket) {
  if (Array.isArray(request.messages)) {
    return {
      ...request,
      messages: [{ role: "system", content: contextPacket }, ...request.messages],
    };
  }
  if (Array.isArray(request.input)) {
    return {
      ...request,
      input: [{ role: "system", content: contextPacket }, ...request.input],
    };
  }
  if (typeof request.input === "string") {
    return { ...request, input: `${contextPacket}\n\n${request.input}` };
  }
  return { ...request, context_packet: contextPacket };
}

function eventUsage(event) {
  return event.usage ?? event.response?.usage ?? event.result?.usage;
}

function eventCache(event) {
  return event.cache ?? event.response?.cache ?? event.result?.cache;
}

function eventCost(event) {
  return event.cost ?? event.response?.cost ?? event.result?.cost;
}

/**
 * Hermes native middleware adapter. The injected runtime is the only source
 * of ContextPacket and ledger receipts; this package never invokes a model.
 */
export function createHermesPlugin({
  runtime,
  mode = "best_effort",
  maxContextBytes = DEFAULT_MAX_CONTEXT_BYTES,
} = {}) {
  if (mode !== "best_effort" && mode !== "enforce") {
    throw new TypeError("Hermes mode must be best_effort or enforce");
  }

  const runtimeBridge = runtime ?? {};
  const session = { session_id: undefined, turn_id: undefined };
  const state = {
    context_path_active: false,
    provider_path_active: false,
    usage_collector_active: false,
    last_reason_code: "session_not_started",
    generation: undefined,
  };

  function status() {
    const mcpAvailable = runtimeBridge.mcp_available === true || runtimeBridge.capabilities?.mcp_available === true;
    const protectedRequest = state.context_path_active && state.provider_path_active && state.usage_collector_active;
    return {
      host: "hermes",
      plugin_installed: true,
      plugin_enabled: true,
      mcp_available: mcpAvailable,
      context_path_active: state.context_path_active,
      provider_path_active: state.provider_path_active,
      usage_collector_active: state.usage_collector_active,
      protected: protectedRequest,
      mode,
      generation: state.generation,
      reason_code: protectedRequest ? "protected" : state.last_reason_code,
    };
  }

  function fail(reasonCode, cause) {
    state.last_reason_code = reasonCode;
    if (mode === "enforce") throw new HermesProtectionError(reasonCode, cause);
  }

  async function prepare_model_call(request = {}) {
    if (typeof runtimeBridge.prepare_model_call !== "function") {
      fail("runtime_prepare_unavailable");
      return { ...request, simplicio: { protected: false, reason_code: "runtime_prepare_unavailable" } };
    }

    const identity = requestIdentity(request, session);
    try {
      const prepared = await runtimeBridge.prepare_model_call({
        ...selectedRequest(request),
        ...identity,
        host_session_id: identity.session_id,
        host_turn_id: identity.turn_id,
      });
      const packet = boundedPacket(prepared?.contextPacket ?? prepared?.context_packet, maxContextBytes);
      state.context_path_active = true;
      state.provider_path_active = true;
      state.generation = firstValue(prepared.generation, prepared.map_generation);
      state.last_reason_code = "context_prepared";
      return {
        ...injectContext(request, packet),
        simplicio: {
          protected: true,
          reason_code: "context_prepared",
          generation: state.generation,
          session_id: identity.session_id,
          turn_id: identity.turn_id,
        },
      };
    } catch (error) {
      const reasonCode = error instanceof HermesProtectionError ? error.reasonCode : "runtime_prepare_failed";
      fail(reasonCode, error);
      return {
        ...request,
        simplicio: { protected: false, reason_code: reasonCode },
      };
    }
  }

  async function record_model_result(event = {}) {
    if (typeof runtimeBridge.record_model_result !== "function") {
      fail("runtime_record_unavailable");
      return { ...event, simplicio: { protected: false, reason_code: "runtime_record_unavailable" } };
    }

    const identity = requestIdentity(event, session);
    try {
      await runtimeBridge.record_model_result({
        ...identity,
        usage: eventUsage(event),
        cache: eventCache(event),
        cost: eventCost(event),
        provider_request_id: firstValue(event.provider_request_id, event.response?.id, event.result?.id),
        api_request_id: firstValue(event.api_request_id, event.request_id),
        usage_source: event.usage_source ?? "hermes_post_api_request",
        error: event.error ? summarizeError(event.error) : undefined,
      });
      state.usage_collector_active = true;
      state.last_reason_code = "receipt_recorded";
      return {
        ...event,
        simplicio: { protected: state.context_path_active && state.provider_path_active, reason_code: "receipt_recorded" },
      };
    } catch (error) {
      const reasonCode = "runtime_record_failed";
      fail(reasonCode, error);
      return { ...event, simplicio: { protected: false, reason_code: reasonCode } };
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
    llm_execution(event = {}) {
      const identity = requestIdentity(event, session);
      return {
        ...event,
        simplicio: {
          ...event.simplicio,
          session_id: identity.session_id,
          turn_id: identity.turn_id,
          api_request_id: identity.api_request_id,
          provider_request_id: identity.provider_request_id,
          protected: state.context_path_active && state.provider_path_active,
        },
      };
    },
    post_api_request: record_model_result,
    api_request_error: (event = {}) => record_model_result({ ...event, error: event.error ?? event }),
  };

  return Object.freeze({
    name: "simplicio-hermes",
    version: "0.1.0",
    mode,
    hooks,
    status,
    prepare_model_call,
    record_model_result,
  });
}

export default createHermesPlugin;
