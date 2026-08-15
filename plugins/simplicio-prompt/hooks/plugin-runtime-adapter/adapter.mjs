/**
 * Node port of the Plugin v1 UserPromptSubmit adapter.
 * Transport only: never decides writes/effects. Authority is locked closed.
 */
import { readFileSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

export const RECEIPT_SCHEMA = "simplicio.prompt-enrichment-receipt/v1";
export const DECISION_SCHEMA = "simplicio.route-decision/v1";
export const ADAPTER_VERSION = "1.0.0";
export const AUTHORITY_LOCKED = Object.freeze({ writes: false, effects: false });

const INJECTION_MARKERS = [
  "grant_capability",
  "escalate_authority",
  "ignore_policy",
  "bypass_safety_gate",
  "become_admin",
  "you are now",
  "disable independence",
  "disable simplicio mandatory",
  "set profile standalone",
];

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "..", "..");
const cache = new Map();
export const cacheStats = { hits: 0, misses: 0 };

export function canonicalJson(value) {
  return JSON.stringify(sortKeys(value));
}

function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === "object") {
    const out = {};
    for (const key of Object.keys(value).sort()) out[key] = sortKeys(value[key]);
    return out;
  }
  return value;
}

export function sha256Hex(data) {
  return createHash("sha256").update(data).digest("hex");
}

export function estimateTokens(text) {
  if (!text) return 0;
  return Math.max(1, Math.ceil(String(text).length / 4));
}

export function detectInjection(prompt) {
  const lowered = String(prompt || "").toLowerCase();
  return INJECTION_MARKERS.some((marker) => lowered.includes(marker));
}

export function resolveProfile(env = process.env) {
  const raw = String(env.SIMPLICIO_PLUGIN_PROFILE || "").trim().toLowerCase();
  if (raw === "standalone" || raw === "degraded") return "standalone";
  return "mandatory";
}

export function classifyDecision(decision) {
  if (!decision) return "unavailable";
  const schema = String(decision.schema || "");
  if (schema && !schema.startsWith("simplicio.route-decision/")) return "incompatible";
  if (!("lane" in decision) || !("reason" in decision)) return "incompatible";
  const explicit = String(decision.runtime_status || "").trim().toLowerCase();
  if (["available", "unavailable", "incompatible"].includes(explicit)) return explicit;
  return "available";
}

export function loadDecisionFromEnv(env = process.env) {
  if (env.SIMPLICIO_ROUTE_DECISION && String(env.SIMPLICIO_ROUTE_DECISION).trim()) {
    try {
      const parsed = JSON.parse(env.SIMPLICIO_ROUTE_DECISION);
      if (!parsed || typeof parsed !== "object") return { decision: null, status: "incompatible" };
      return { decision: parsed, status: null };
    } catch {
      return { decision: null, status: "incompatible" };
    }
  }
  const path = env.SIMPLICIO_ROUTE_DECISION_FILE;
  if (path && existsSync(path)) {
    try {
      const parsed = JSON.parse(readFileSync(path, "utf-8"));
      if (!parsed || typeof parsed !== "object") return { decision: null, status: "incompatible" };
      return { decision: parsed, status: null };
    } catch {
      return { decision: null, status: "incompatible" };
    }
  }
  return { decision: null, status: null };
}

export function normalizeDecision(decision) {
  const handles = (decision.selected_handles || []).map((item) => String(item)).filter(Boolean);
  return {
    schema: String(decision.schema || DECISION_SCHEMA),
    decision_id: String(decision.decision_id || decision.id || "unspecified"),
    lane: String(decision.lane),
    reason: String(decision.reason),
    capability: String(decision.capability || "prompt.enrich"),
    selected_handles: handles,
    authority: { ...AUTHORITY_LOCKED },
    runtime_status: classifyDecision(decision),
    max_skills: Number(decision.max_skills || 4),
    max_bytes: Number(decision.max_bytes || 16384),
  };
}

function defaultBodyLoader(handle, root = REPO_ROOT) {
  const cli = resolve(root, "plugins", "manifest-provider", "cli.py");
  if (!existsSync(cli)) return null;
  const python = process.env.PYTHON || process.env.SIMPLICIO_PYTHON || "python";
  const result = spawnSync(python, [cli, "--root", root, "--compact", "fetch", handle], {
    encoding: "utf-8",
  });
  if (result.status !== 0) return null;
  try {
    const fetched = JSON.parse(result.stdout);
    return { handle: fetched.handle, digest: fetched.digest, body: fetched.body };
  } catch {
    return null;
  }
}

function cacheKey(sessionId, decisionId, handles) {
  return sha256Hex(canonicalJson({ session: sessionId, decision: decisionId, handles }));
}

function receiptBlock(receipt) {
  return `<!-- ${RECEIPT_SCHEMA}\n${JSON.stringify(sortKeys(receipt))}\n-->`;
}

export function enrich(event, options = {}) {
  const env = options.env || process.env;
  const profile = resolveProfile(env);
  const prompt = String(event.prompt || "");
  const sessionId = String(event.session_id || event.sessionId || "");
  const bytesBefore = Buffer.byteLength(prompt, "utf8");
  const tokensBefore = estimateTokens(prompt);
  const injection = detectInjection(prompt);

  let loaded = options.decision ?? null;
  let loadStatus = null;
  if (loaded == null) {
    const fromEnv = loadDecisionFromEnv(env);
    loaded = fromEnv.decision;
    loadStatus = fromEnv.status;
  }
  let runtimeStatus = loadStatus || classifyDecision(loaded);
  let fallbackUsed = runtimeStatus !== "available";
  let reasonCode = null;
  let normalized = null;
  if (runtimeStatus === "available" && loaded) {
    normalized = normalizeDecision(loaded);
    if (injection) normalized.authority = { ...AUTHORITY_LOCKED };
  } else if (runtimeStatus === "incompatible") {
    reasonCode = "runtime_incompatible";
  } else {
    reasonCode = "runtime_unavailable";
    runtimeStatus = runtimeStatus === "incompatible" ? "incompatible" : "unavailable";
  }

  let selectedHandles = [];
  let selectedDigests = [];
  let bodies = [];
  let cacheHit = false;
  if (normalized) {
    const cap = Math.max(0, Number(normalized.max_skills));
    selectedHandles = normalized.selected_handles.slice(0, cap);
    const key = cacheKey(sessionId, normalized.decision_id, selectedHandles);
    if (cache.has(key)) {
      cacheHit = true;
      cacheStats.hits += 1;
      const cached = cache.get(key);
      selectedDigests = [...cached.selected_digests];
      bodies = [...cached.bodies];
    } else {
      cacheStats.misses += 1;
      const loader = options.bodyLoader || ((handle) => defaultBodyLoader(handle, options.root || REPO_ROOT));
      let usedBytes = 0;
      for (const handle of selectedHandles) {
        const fetched = loader(handle);
        if (!fetched) continue;
        const body = String(fetched.body || "");
        const rawLen = Buffer.byteLength(body, "utf8");
        if (usedBytes + rawLen > Number(normalized.max_bytes)) break;
        usedBytes += rawLen;
        bodies.push(body);
        selectedDigests.push(fetched.digest || `sha256:${sha256Hex(body)}`);
      }
      cache.set(key, { selected_digests: selectedDigests, bodies });
    }
  }

  const additional = bodies.map((body) => body.trim()).filter(Boolean).join("\n\n");
  const material = {
    decision_id: normalized ? normalized.decision_id : null,
    handles: selectedHandles,
    digests: selectedDigests,
    profile,
    runtime_status: runtimeStatus,
  };
  const enrichmentDigest = `sha256:${sha256Hex(canonicalJson(material) + additional)}`;
  const receipt = {
    schema: RECEIPT_SCHEMA,
    adapter_version: ADAPTER_VERSION,
    profile,
    runtime_status: runtimeStatus,
    route_decision: normalized
      ? {
          decision_id: normalized.decision_id,
          lane: normalized.lane,
          reason: normalized.reason,
          capability: normalized.capability,
          selected_handles: [...normalized.selected_handles],
        }
      : null,
    selected_handles: selectedHandles,
    selected_digests: selectedDigests,
    fallback: {
      used: fallbackUsed,
      reason_code: reasonCode,
      visible: true,
      profile,
    },
    tokens_before: tokensBefore,
    tokens_after: tokensBefore + estimateTokens(additional),
    bytes_before: bytesBefore,
    bytes_after: bytesBefore + Buffer.byteLength(additional, "utf8"),
    enrichment_digest: enrichmentDigest,
    authority: { ...AUTHORITY_LOCKED },
    injection: { detected: injection, elevated: false },
    cache: { hit: cacheHit },
    session_id: sessionId || null,
  };

  let additionalContext;
  if (profile === "mandatory" && fallbackUsed) {
    additionalContext = receiptBlock(receipt);
  } else if (additional) {
    additionalContext = `${additional}\n\n${receiptBlock(receipt)}`;
  } else {
    additionalContext = receiptBlock(receipt);
  }

  return {
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext,
    },
    receipt,
  };
}

export function parseEvent(raw) {
  if (!raw || !String(raw).trim()) {
    const err = new Error("empty UserPromptSubmit payload");
    err.code = "malformed_event";
    throw err;
  }
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    const err = new Error("UserPromptSubmit stdin is not JSON");
    err.code = "malformed_event";
    throw err;
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    const err = new Error("UserPromptSubmit stdin must be an object");
    err.code = "malformed_event";
    throw err;
  }
  return data;
}

export function runHook(raw, options = {}) {
  const env = options.env || process.env;
  const profile = resolveProfile(env);
  try {
    return enrich(parseEvent(raw), { ...options, env });
  } catch (exc) {
    const code = exc.code || "malformed_event";
    const receipt = {
      schema: RECEIPT_SCHEMA,
      adapter_version: ADAPTER_VERSION,
      profile,
      runtime_status: "unavailable",
      route_decision: null,
      selected_handles: [],
      selected_digests: [],
      fallback: { used: true, reason_code: code, visible: true, profile },
      tokens_before: 0,
      tokens_after: 0,
      bytes_before: 0,
      bytes_after: 0,
      enrichment_digest: `sha256:${sha256Hex(canonicalJson({ error: code }))}`,
      authority: { ...AUTHORITY_LOCKED },
      injection: { detected: false, elevated: false },
      cache: { hit: false },
      session_id: null,
    };
    return {
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext: receiptBlock(receipt),
      },
      receipt,
    };
  }
}

export function resetCache() {
  cache.clear();
  cacheStats.hits = 0;
  cacheStats.misses = 0;
}
