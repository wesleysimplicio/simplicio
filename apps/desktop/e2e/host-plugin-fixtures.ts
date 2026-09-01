export const NATIVE_HOSTS = [
  "codex",
  "claude",
  "gemini",
  "copilot",
  "qwen",
  "hermes",
  "cursor",
  "kiro",
] as const;

type ReceiptState = "complete" | "partial" | "requires_reconcile";
type HostStatus = "verified" | "applied_unverified" | "blocked" | "failed";

export function hostPluginPlan(digestByte = "a") {
  return {
    schema: "simplicio.host-plugin-command-result/v1",
    result: "plan",
    plan: {
      schema: "simplicio.host-plugin-plan-summary/v1",
      plan_digest: `sha256:${digestByte.repeat(64)}`,
      selection: { scope: "all" },
      manifest_digest: `sha256:${"f".repeat(64)}`,
      plugin_version: "3.8.41",
      component_versions: { runtime: "3.8.41", plugin: "3.8.41" },
      hosts: NATIVE_HOSTS.map((host, index) => ({
        host,
        mode: index >= 6 ? "portable" : "manager",
        disposition: index === 7 ? "not_detected" : "ready",
        reason_code: index === 7 ? "not_detected" : "ready",
      })),
    },
  };
}

export function hostPluginReceipt({
  planDigestByte = "a",
  state = "complete",
  status = "verified",
  operation = "apply",
  receiptByte = "c",
  durableByte = "d",
}: {
  planDigestByte?: string;
  state?: ReceiptState;
  status?: HostStatus;
  operation?: "apply" | "reconcile";
  receiptByte?: string;
  durableByte?: string;
} = {}) {
  return {
    schema: "simplicio.host-plugin-command-result/v1",
    result: "receipt",
    receipt: { schema: "simplicio.host-plugin-receipt/v1", redacted: true },
    snapshot: {
      schema: "simplicio.host-plugin-snapshot/v1",
      receipt_schema: "simplicio.host-plugin-receipt/v1",
      receipt_digest: `sha256:${receiptByte.repeat(64)}`,
      operation,
      state,
      attempt_id: `attempt-${receiptByte}`,
      revision: 1,
      durable_id: `sha256:${durableByte.repeat(64)}`,
      plan_digest: `sha256:${planDigestByte.repeat(64)}`,
      observed_plan_digest: `sha256:${planDigestByte.repeat(64)}`,
      manifest_digest: `sha256:${"f".repeat(64)}`,
      hosts: NATIVE_HOSTS.map((host, index) => {
        const hostStatus = state === "partial" && index === 0 ? "failed" : status;
        return {
          host,
          status: hostStatus,
          reason_code: hostStatus === "verified" ? "exact_readback"
            : hostStatus === "applied_unverified" ? "manager_readback_unknown"
              : hostStatus === "blocked" ? "precondition_blocked" : "effect_failed",
          ...(hostStatus === "failed" ? { failure_code: "manager_effect_failed" } : {}),
          verification: hostStatus === "verified" ? "installed_tree_and_manager" : "none",
          ...(state === "partial" ? { reconcile: hostStatus === "failed" ? "ambiguous" : "committed" } : {}),
        };
      }),
    },
  };
}

export function desktopHostPluginProjection({ pending = false, status = "verified" as HostStatus } = {}) {
  const receipt = hostPluginReceipt({ state: pending ? "partial" : "complete", status }).snapshot;
  return {
    schema: "simplicio.desktop-host-plugins/v1",
    available: true,
    reconcileRequired: pending,
    ...(pending ? { reconcileReceiptId: `sha256:${"e".repeat(64)}` } : {}),
    pendingCount: pending ? 1 : 0,
    pendingTruncated: false,
    state: receipt.state,
    revision: 1,
    receiptDigest: receipt.receipt_digest,
    planDigest: receipt.plan_digest,
    hosts: receipt.hosts.map((host) => ({
      host: host.host,
      status: host.status,
      reasonCode: host.reason_code,
      ...("failure_code" in host && host.failure_code ? { failureCode: host.failure_code } : {}),
      verification: host.verification,
      ...("reconcile" in host && host.reconcile ? { reconcile: host.reconcile } : {}),
    })),
  };
}
