import type { AccessState, DesktopSnapshot, ProviderConnection } from "./contracts";

type DemoProvider = Pick<ProviderConnection, "id" | "name" | "kind" | "protocol" | "tier" | "state" | "detail">;

function demoProvider(provider: DemoProvider): ProviderConnection {
  const installed = provider.state !== "not_installed";
  const registered = provider.state === "connected" || provider.state === "needs_attention";
  return {
    ...provider,
    installState: installed ? "installed" : "absent",
    registrationState: registered ? "registered" : "unregistered",
    handshakeState: provider.state === "connected" ? "live" : "unverified",
    freshness: "current",
    reasonCode: !installed
      ? "host_not_installed"
      : provider.state === "needs_attention"
        ? "handshake_failed"
        : provider.state === "detected"
          ? "host_detected"
          : "handshake_not_observed",
    availableActions: !installed ? ["register"] : registered ? ["verify", "repair"] : ["register"],
  };
}

const providers: DesktopSnapshot["providers"] = [
  demoProvider({ id: "codex", name: "OpenAI Codex", kind: "agent", protocol: "Plugin", tier: "first_class", state: "detected", detail: "Registrado; aguardando sessão" }),
  demoProvider({ id: "claude-code", name: "Claude Code", kind: "agent", protocol: "MCP", tier: "first_class", state: "needs_attention", detail: "Configuração pendente" }),
  demoProvider({ id: "opencode", name: "OpenCode", kind: "agent", protocol: "CLI", tier: "compatible", state: "detected", detail: "Registrado; aguardando sessão" }),
  demoProvider({ id: "grok", name: "Grok", kind: "agent", protocol: "MCP", tier: "compatible", state: "not_installed", detail: "Não encontrado" }),
  demoProvider({ id: "hermes", name: "Hermes", kind: "agent", protocol: "MCP", tier: "compatible", state: "detected", detail: "Registrado; aguardando sessão" }),
  demoProvider({ id: "gemini", name: "Gemini CLI", kind: "agent", protocol: "CLI", tier: "compatible", state: "not_installed", detail: "Não encontrado" }),
  demoProvider({ id: "vscode", name: "VS Code / Cline", kind: "editor", protocol: "MCP", tier: "first_class", state: "needs_attention", detail: "Configuração pendente" }),
  demoProvider({ id: "cursor", name: "Cursor", kind: "editor", protocol: "MCP", tier: "first_class", state: "not_installed", detail: "Não encontrado" }),
  demoProvider({ id: "windsurf", name: "Windsurf", kind: "editor", protocol: "MCP", tier: "compatible", state: "not_installed", detail: "Não encontrado" }),
  demoProvider({ id: "kiro", name: "Kiro", kind: "editor", protocol: "MCP", tier: "first_class", state: "not_installed", detail: "Não encontrado" }),
  demoProvider({ id: "zed", name: "Zed", kind: "editor", protocol: "MCP", tier: "compatible", state: "not_installed", detail: "Não encontrado" }),
  demoProvider({ id: "jetbrains", name: "JetBrains", kind: "editor", protocol: "Plugin", tier: "compatible", state: "not_installed", detail: "Não encontrado" }),
  demoProvider({ id: "orca", name: "Orca", kind: "agent", protocol: "Plugin", tier: "first_class", state: "needs_attention", detail: "Configuração pendente" }),
  demoProvider({ id: "antigravity", name: "Antigravity", kind: "editor", protocol: "MCP", tier: "compatible", state: "not_installed", detail: "Não encontrado" }),
];

export function createDemoSnapshot(state: AccessState = "active"): DesktopSnapshot {
  const generatedAt = new Date().toISOString();
  const identityKnown = state !== "signed_out";
  const entitlementKnown = state === "active" || state === "inactive";
  const actions: DesktopSnapshot["actions"] = state === "signed_out"
    ? [{ id: "login", governed: true, executed: false }]
    : state === "inactive"
      ? [
          { id: "subscribe", governed: true, executed: false },
          { id: "refresh_access", governed: true, executed: false },
        ]
      : state === "unknown"
        ? [{ id: "refresh_access", governed: true, executed: false }]
        : [];

  return {
    schema: "simplicio.desktop-snapshot/v1",
    generatedAt,
    source: "preview",
    access: {
      state,
      identityKnown,
      entitlementKnown,
      reasonCode: state === "signed_out"
        ? "local_identity_missing"
        : state === "inactive"
          ? "entitlement_inactive"
          : state === "active"
            ? "entitlement_active"
            : "auth_validation_unavailable",
      checkedAt: generatedAt,
      expiresAt: state === "active" ? "2026-09-12T00:00:00Z" : null,
      displayName: identityKnown ? "Você" : null,
      email: identityKnown ? "voce@example.com" : null,
      plan: state === "active" ? "Simplicio MCP" : null,
    },
    runtime: {
      state: "healthy",
      version: "3.8.36",
      transport: "sidecar",
      lastReceiptAt: generatedAt,
      deterministic: {
        ready: true,
        cpuFirst: true,
        mapper: "canonical",
        mapCache: "generation_scoped",
        hookContext: "receipt_only",
      },
      optionalFast: {
        required: false,
        hookInjected: false,
        status: "not_required",
      },
    },
    savings: {
      monthTokens: 1_842_610,
      monthPercent: 71.4,
      estimatedUsd: 42.86,
      proofKind: "mixed",
      ledgerStatus: "valid",
      eventCount: 184,
      providerCache: {
        status: "unknown",
        hitPercent: null,
        proofKind: "unavailable",
        telemetrySource: null,
      },
      decisionCache: {
        hitPercent: 68.2,
        runs: 184,
        proofKind: "measured",
        hits: 125,
      },
      mapCache: {
        status: "ready",
        delivery: "receipt_only",
        generation: "preview-20260828",
        digest: `sha256:${"a".repeat(64)}`,
        bytes: 32_768,
        fastInHooks: false,
      },
    },
    providers,
    activity: [
      {
        id: "a1",
        title: "Contexto reutilizado",
        detail: "Recibo verificado",
        provider: "Codex",
        savedTokens: 18_420,
        occurredAt: generatedAt,
        status: "verified",
      },
      {
        id: "a2",
        title: "Validação determinística",
        detail: "Recibo verificado",
        provider: "Runtime",
        savedTokens: 8_910,
        occurredAt: generatedAt,
        status: "verified",
      },
    ],
    actions,
    freshness: {
      access: generatedAt,
      runtime: generatedAt,
      savings: generatedAt,
      providers: generatedAt,
    },
    redaction: {
      personalPaths: true,
      configurationBodies: true,
      credentials: true,
      prompts: true,
      skillBodies: true,
      rawLedgers: true,
    },
    limits: {
      maxBytes: 65_536,
      maxProviders: 32,
      maxActivity: 5,
    },
    snapshotDigest: `sha256:${"b".repeat(64)}`,
  };
}
