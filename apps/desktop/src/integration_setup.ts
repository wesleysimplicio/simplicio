export const HOST_PLUGIN_IDS = [
  "codex",
  "claude",
  "gemini",
  "copilot",
  "qwen",
  "hermes",
  "cursor",
  "kiro",
] as const;

export type HostPluginId = typeof HOST_PLUGIN_IDS[number];
export type HostPluginMode = "manager" | "portable" | "hybrid";
export type HostPluginPlanDisposition = "ready" | "already_exact" | "not_detected" | "unknown" | "blocked";
export type HostPluginReceiptState = "prepared" | "applying" | "complete" | "partial" | "requires_reconcile";
export type HostPluginResultStatus =
  | "pending"
  | "applying"
  | "verified"
  | "applied_unverified"
  | "not_detected"
  | "unknown"
  | "failed"
  | "drifted"
  | "blocked";
export type HostPluginVerification = "none" | "manager_version" | "installed_tree" | "installed_tree_and_manager";
export type HostPluginReconcile = "committed" | "not_applied" | "partial" | "drifted" | "ambiguous" | "not_applicable";

const DIGEST = /^sha256:[a-f0-9]{64}$/;
const VERSION = /^[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}$/;
const HOSTS = new Set<string>(HOST_PLUGIN_IDS);
const MODES = new Set<string>(["manager", "portable", "hybrid"]);
const DISPOSITIONS = new Set<string>(["ready", "already_exact", "not_detected", "unknown", "blocked"]);
const PLAN_REASONS = new Set<string>(["ready", "already_exact", "not_detected", "unknown", "blocked", "local_install_capability_unverified"]);
const RECEIPT_STATES = new Set<string>(["prepared", "applying", "complete", "partial", "requires_reconcile"]);
const RESULT_STATUSES = new Set<string>(["pending", "applying", "verified", "applied_unverified", "not_detected", "unknown", "failed", "drifted", "blocked"]);
const REASON_CODES = new Set<string>([
  "awaiting_effect", "already_exact", "host_or_manager_not_detected", "state_unknown", "precondition_blocked",
  "effect_prepared", "manager_version_verified", "manager_readback_drifted", "manager_readback_unknown",
  "portable_tree_verified", "exact_readback", "portable_payload_not_exact", "manager_plugin_drifted",
  "local_install_capability_unverified", "effect_failed", "reconcile_committed", "reconcile_not_applied",
  "reconcile_partial", "reconcile_drifted", "reconcile_ambiguous", "no_action_required",
]);
const FAILURE_CODES = new Set<string>([
  "manager_unavailable", "manager_precondition_changed", "manager_effect_failed", "manager_readback_failed",
  "payload_changed", "portable_busy", "portable_precondition_changed", "portable_stage_failed",
  "portable_backup_failed", "portable_publish_failed", "portable_readback_failed", "receipt_persistence_failed",
  "internal_contract",
]);
const VERIFICATIONS = new Set<string>(["none", "manager_version", "installed_tree", "installed_tree_and_manager"]);
const RECONCILE = new Set<string>(["committed", "not_applied", "partial", "drifted", "ambiguous", "not_applicable"]);

export interface IntegrationPlanHost {
  host: HostPluginId;
  mode: HostPluginMode;
  disposition: HostPluginPlanDisposition;
  reasonCode: string;
}

/** Bounded Runtime plan projected for review. It never contains commands or filesystem data. */
export interface IntegrationPlan {
  schema: "simplicio.host-plugin-plan-summary/v1";
  source: "runtime" | "preview";
  planDigest: string;
  manifestDigest: string;
  pluginVersion: string;
  hosts: IntegrationPlanHost[];
}

export interface HostPluginSnapshotHost {
  host: HostPluginId;
  status: HostPluginResultStatus;
  reasonCode: string;
  failureCode: string | null;
  verification: HostPluginVerification;
  reconcile: HostPluginReconcile | null;
}

export interface DesktopHostPluginHost {
  host: HostPluginId;
  status: HostPluginResultStatus;
  reasonCode: string;
  failureCode?: string;
  verification: HostPluginVerification;
  reconcile?: HostPluginReconcile;
}

/** Safe canonical projection of a Runtime-owned durable receipt. */
export interface HostPluginSnapshot {
  schema: "simplicio.host-plugin-snapshot/v1";
  receiptDigest: string;
  operation: "apply" | "reconcile";
  state: HostPluginReceiptState;
  receiptId: string | null;
  planDigest: string;
  hosts: HostPluginSnapshotHost[];
}

export interface DesktopHostPlugins {
  schema: "simplicio.desktop-host-plugins/v1";
  available: boolean;
  reconcileRequired: boolean;
  pendingCount: number;
  pendingTruncated: boolean;
  state?: HostPluginReceiptState;
  revision?: number;
  receiptDigest?: string;
  reconcileReceiptId?: string;
  planDigest?: string;
  hosts: DesktopHostPluginHost[];
}

export interface HostPluginOperationResult {
  schema: "simplicio.host-plugin-command-result/v1";
  result: "receipt";
  snapshot: HostPluginSnapshot;
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("host_plugin_contract_invalid");
  return value as Record<string, unknown>;
}

function digest(value: unknown): string {
  if (typeof value !== "string" || !DIGEST.test(value)) throw new Error("host_plugin_contract_invalid");
  return value;
}

function optionalDigest(value: unknown): string | null {
  return value === undefined || value === null ? null : digest(value);
}

function closed<T extends string>(value: unknown, values: Set<string>): T {
  if (typeof value !== "string" || !values.has(value)) throw new Error("host_plugin_contract_invalid");
  return value as T;
}

function uniqueHosts<T extends { host: HostPluginId }>(hosts: T[], exact: boolean): T[] {
  if (hosts.length > HOST_PLUGIN_IDS.length || (exact && hosts.length !== HOST_PLUGIN_IDS.length)
    || new Set(hosts.map(({ host }) => host)).size !== hosts.length) throw new Error("host_plugin_hosts_invalid");
  if (exact && HOST_PLUGIN_IDS.some((host) => !hosts.some((candidate) => candidate.host === host))) {
    throw new Error("host_plugin_hosts_invalid");
  }
  return hosts;
}

function planHost(value: unknown): IntegrationPlanHost {
  const row = record(value);
  return {
    host: closed<HostPluginId>(row.host, HOSTS),
    mode: closed<HostPluginMode>(row.mode, MODES),
    disposition: closed<HostPluginPlanDisposition>(row.disposition, DISPOSITIONS),
    reasonCode: closed<string>(row.reason_code, PLAN_REASONS),
  };
}

export function integrationChangeLabel(host: IntegrationPlanHost): string {
  switch (host.disposition) {
    case "ready": return host.mode === "portable" ? "Pronto para instalar" : "Pronto para configurar";
    case "already_exact": return "Já atualizado";
    case "not_detected": return "Aplicativo não detectado";
    case "unknown": return "Estado não confirmado";
    case "blocked": return host.reasonCode === "local_install_capability_unverified" ? "Instalação manual" : "Bloqueado";
  }
}

export function parseIntegrationPlan(value: unknown, source: "runtime" | "preview" = "runtime"): IntegrationPlan {
  const envelope = record(value);
  const raw = envelope.schema === "simplicio.host-plugin-command-result/v1" && envelope.result === "plan"
    ? record(envelope.plan)
    : envelope;
  if (raw.schema !== "simplicio.host-plugin-plan-summary/v1") throw new Error("integration_plan_invalid");
  const selection = record(raw.selection);
  if (selection.scope !== "all" || Object.keys(selection).length !== 1) throw new Error("integration_plan_selection_invalid");
  if (typeof raw.plugin_version !== "string" || !VERSION.test(raw.plugin_version) || !Array.isArray(raw.hosts)) {
    throw new Error("integration_plan_invalid");
  }
  const hosts = uniqueHosts(raw.hosts.map(planHost), true);
  return {
    schema: "simplicio.host-plugin-plan-summary/v1",
    source,
    planDigest: digest(raw.plan_digest),
    manifestDigest: digest(raw.manifest_digest),
    pluginVersion: raw.plugin_version,
    hosts,
  };
}

function snapshotHost(value: unknown): HostPluginSnapshotHost {
  const row = record(value);
  const failureCode = row.failure_code === undefined || row.failure_code === null
    ? null
    : closed<string>(row.failure_code, FAILURE_CODES);
  const reconcile = row.reconcile === undefined || row.reconcile === null
    ? null
    : closed<HostPluginReconcile>(row.reconcile, RECONCILE);
  return {
    host: closed<HostPluginId>(row.host, HOSTS),
    status: closed<HostPluginResultStatus>(row.status, RESULT_STATUSES),
    reasonCode: closed<string>(row.reason_code, REASON_CODES),
    failureCode,
    verification: closed<HostPluginVerification>(row.verification, VERIFICATIONS),
    reconcile,
  };
}

export function parseHostPluginSnapshot(value: unknown): HostPluginSnapshot {
  const snapshot = record(value);
  if (snapshot.schema !== "simplicio.host-plugin-snapshot/v1" || !Array.isArray(snapshot.hosts)) {
    throw new Error("host_plugin_snapshot_invalid");
  }
  const operation = closed<HostPluginSnapshot["operation"]>(snapshot.operation, new Set(["apply", "reconcile"]));
  const state = closed<HostPluginReceiptState>(snapshot.state, RECEIPT_STATES);
  const hosts = uniqueHosts(snapshot.hosts.map(snapshotHost), false);
  const receiptId = optionalDigest(snapshot.durable_id);
  if ((state === "partial" || state === "requires_reconcile") && receiptId === null) {
    throw new Error("host_plugin_receipt_id_missing");
  }
  return {
    schema: "simplicio.host-plugin-snapshot/v1",
    receiptDigest: digest(snapshot.receipt_digest),
    operation,
    state,
    receiptId,
    planDigest: digest(snapshot.plan_digest),
    hosts,
  };
}

export function parseHostPluginOperationResult(value: unknown, expectedOperation?: "apply" | "reconcile"): HostPluginOperationResult {
  const result = record(value);
  if (result.schema !== "simplicio.host-plugin-command-result/v1" || result.result !== "receipt") {
    throw new Error("host_plugin_operation_invalid");
  }
  const snapshot = parseHostPluginSnapshot(result.snapshot);
  if (expectedOperation && snapshot.operation !== expectedOperation) throw new Error("host_plugin_operation_mismatch");
  if (!(["complete", "partial", "requires_reconcile"] as HostPluginReceiptState[]).includes(snapshot.state)) {
    throw new Error("host_plugin_operation_incomplete");
  }
  return { schema: "simplicio.host-plugin-command-result/v1", result: "receipt", snapshot };
}

export function hostPluginOutcomeLabel(snapshot: HostPluginSnapshot): string {
  if (snapshot.state === "requires_reconcile") return "Reconciliação necessária";
  if (snapshot.state === "partial") return "Aplicação parcial";
  if (snapshot.hosts.some(({ status }) => status === "blocked")) return "Concluído com ações manuais";
  if (snapshot.hosts.some(({ status }) => status === "applied_unverified")) return "Aplicado; verificação indisponível";
  return snapshot.state === "complete" ? "Configuração concluída" : "Operação em andamento";
}

export function createPreviewDesktopHostPlugins(): DesktopHostPlugins {
  const plan = createPreviewIntegrationPlan();
  const snapshot = createPreviewHostPluginResult(plan.planDigest).snapshot;
  return {
    schema: "simplicio.desktop-host-plugins/v1",
    available: true,
    reconcileRequired: false,
    pendingCount: 0,
    pendingTruncated: false,
    state: snapshot.state,
    revision: 1,
    receiptDigest: snapshot.receiptDigest,
    planDigest: snapshot.planDigest,
    hosts: snapshot.hosts.map(({ failureCode, reconcile, ...host }) => ({
      ...host,
      ...(failureCode ? { failureCode } : {}),
      ...(reconcile ? { reconcile } : {}),
    })),
  };
}

export function createPreviewIntegrationPlan(): IntegrationPlan {
  return {
    schema: "simplicio.host-plugin-plan-summary/v1",
    source: "preview",
    planDigest: `sha256:${"0".repeat(64)}`,
    manifestDigest: `sha256:${"1".repeat(64)}`,
    pluginVersion: "preview",
    hosts: HOST_PLUGIN_IDS.map((host, index) => ({
      host,
      mode: host === "cursor" || host === "kiro" ? "portable" : "manager",
      disposition: index < 2 ? "ready" : index < 5 ? "already_exact" : "not_detected",
      reasonCode: index < 2 ? "ready" : index < 5 ? "already_exact" : "not_detected",
    })),
  };
}

export function createPreviewHostPluginResult(planDigest: string, operation: "apply" | "reconcile" = "apply"): HostPluginOperationResult {
  if (!DIGEST.test(planDigest)) throw new Error("host_plugin_contract_invalid");
  return {
    schema: "simplicio.host-plugin-command-result/v1",
    result: "receipt",
    snapshot: {
      schema: "simplicio.host-plugin-snapshot/v1",
      receiptDigest: `sha256:${"2".repeat(64)}`,
      operation,
      state: "complete",
      receiptId: `sha256:${"3".repeat(64)}`,
      planDigest,
      hosts: HOST_PLUGIN_IDS.map((host) => ({
        host,
        status: "verified",
        reasonCode: "exact_readback",
        failureCode: null,
        verification: "installed_tree_and_manager",
        reconcile: null,
      })),
    },
  };
}
