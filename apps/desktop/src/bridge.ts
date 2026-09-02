import { invoke } from "@tauri-apps/api/core";
import { open as openFolderDialog } from "@tauri-apps/plugin-dialog";
import type { AccessState, DesktopSnapshot } from "./contracts";
import { createDemoSnapshot } from "./demo";
import type { BotCenterSnapshot } from "./contracts";
import type { BotActionRequest } from "./bot_center";
import { applyDemoBotAction } from "./bot_center";
import { parseTokenExportReceipt, parseTokenUsageReport, type TokenQuery, type TokenUsageReport } from "./token_usage";
import {
  createPreviewHostPluginResult,
  createPreviewIntegrationPlan,
  parseHostPluginOperationResult,
  parseIntegrationPlan,
  type HostPluginOperationResult,
  type IntegrationPlan,
} from "./integration_setup";
import { parseLocalProject, type LocalProject } from "./workbench";
import { createReadonlyRequest } from "./readonly_request";
import { createContextReader } from "./context_report";
import { parseUsageProjects } from "./project_usage";
import { applyUsageChangefeedEvent, createUsageChangefeedState, type UsageChangefeedState } from "./usage_changefeed";
import { exportUnifiedUsageProjection, parseUnifiedUsageProjection, type UnifiedUsageProjection, type UsageQuery } from "./unified_usage";
import { parseCostProjection, type CostProjection, type CostQuery } from "./cost_projection";
import { createConsolidatedReader, type ConsolidatedQuery, type ConsolidatedReport } from "./consolidated_tokens";
import {
  createPreviewRuntimeInstallResult,
  parseRuntimeInstallResult,
  parseRuntimeInstallReconciliation,
  parseRuntimeInstallStatus,
  type RuntimeInstallResult,
  type RuntimeInstallReconciliation,
  type RuntimeInstallStatus,
} from "./runtime_install";

const readSnapshot = createReadonlyRequest<DesktopSnapshot>(30_000, "desktop_snapshot_timeout");
const readContext = createContextReader((repoPath) => invoke<unknown>("desktop_context_report", { repoPath: repoPath || null }));
// Fresh authorization (20s) plus at most four isolated root scans (3s + cleanup each).
const readUsageProjects = createReadonlyRequest<unknown>(45_000, "project_discovery_timeout");
const readConsolidated = createConsolidatedReader(request => invoke<unknown>("desktop_consolidated_token_report", { request }));

export function loadDesktopConsolidatedTokens(request: ConsolidatedQuery): Promise<ConsolidatedReport> {
  if (!isTauri()) return Promise.reject(new Error("preview_no_runtime"));
  return readConsolidated(request);
}

export async function loadDesktopUsageProjects() {
  if (!isTauri()) throw new Error("preview_no_runtime");
  return parseUsageProjects(await readUsageProjects(() => invoke<unknown>("desktop_usage_projects")));
}

export async function loadDesktopUnifiedUsage(query: UsageQuery = {}): Promise<UnifiedUsageProjection> {
  if (!isTauri()) throw new Error("preview_no_runtime");
  return parseUnifiedUsageProjection(await withTimeout(
    invoke<unknown>("desktop_unified_usage", { query }),
    60_000,
    "unified_usage_timeout",
  ));
}

export function exportDesktopUnifiedUsage(
  projection: UnifiedUsageProjection,
  format: "json" | "csv",
): string {
  return exportUnifiedUsageProjection(projection, format);
}

export async function loadDesktopCostProjection(query: CostQuery = {}): Promise<CostProjection> {
  if (!isTauri()) throw new Error("preview_no_runtime");
  return parseCostProjection(await withTimeout(
    invoke<unknown>("desktop_cost_projection", { query }),
    60_000,
    "cost_projection_timeout",
  ));
}

export function loadDesktopContextReport(repoPath: string) {
  if (!isTauri()) return Promise.reject(new Error("preview_no_runtime"));
  return readContext(repoPath);
}

let projectPicker: Promise<LocalProject | null> | null = null;

export function chooseDesktopProject(): Promise<LocalProject | null> {
  if (!isTauri()) return Promise.reject(new Error("preview_no_filesystem"));
  if (projectPicker) return projectPicker;
  projectPicker = (async () => {
    const path = await openFolderDialog({ title: "Adicionar projeto ao Simplicio", directory: true, multiple: false });
    if (path === null) return null;
    if (typeof path !== "string") throw new Error("project_path_invalid");
    // The native validator owns canonicalization and local-path safety even for picker results.
    return validateDesktopProject(path);
  })().finally(() => { projectPicker = null; });
  return projectPicker;
}

export async function validateDesktopProject(path: string): Promise<LocalProject> {
  if (!isTauri()) throw new Error("preview_no_filesystem");
  return parseLocalProject(await invoke<unknown>("desktop_validate_project", { path }));
}

export async function openDesktopProject(path: string): Promise<void> {
  if (!isTauri()) throw new Error("preview_no_filesystem");
  await invoke("desktop_open_project", { path });
}

export async function exportDesktopSnapshot(kind: "diagnostic" | "activity", filters: { status?: string; provider?: string } = {}): Promise<string | null> {
  if (!isTauri()) return null;
  const receipt = await invoke<{ schema: string; path: string; bytes: number }>("desktop_export_snapshot", { kind, filters });
  if (receipt.schema !== "simplicio.desktop-snapshot-export/v1" || typeof receipt.path !== "string" || receipt.bytes <= 0) throw new Error("snapshot_export_invalid");
  return receipt.path;
}

function previewState(): AccessState {
  const requested = new URLSearchParams(window.location.search).get("state");
  if (
    requested === "signed_out" ||
    requested === "inactive" ||
    requested === "active" ||
    requested === "unknown"
  ) {
    return requested;
  }
  return "active";
}

function isTauri(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

export async function loadDesktopSnapshot(): Promise<DesktopSnapshot> {
  if (!isTauri()) {
    return createDemoSnapshot(previewState());
  }

  return readSnapshot(() => invoke<DesktopSnapshot>("desktop_snapshot"));
}

/**
 * Pull one Runtime-owned usage event. The current public Runtime may not
 * expose this command yet; callers keep the last state and surface the
 * capability error instead of showing a false zero.
 */
export async function pullDesktopUsageChangefeed(
  cursor: UsageChangefeedState = createUsageChangefeedState(),
): Promise<UsageChangefeedState> {
  if (!isTauri()) throw new Error("preview_no_runtime");
  const event = await withTimeout(invoke<unknown>("desktop_usage_changefeed", {
    afterSequence: cursor.cursor.sequence,
    afterRevision: cursor.cursor.revision,
  }), 30_000, "usage_changefeed_timeout");
  return applyUsageChangefeedEvent(cursor, event);
}

export async function installDesktopRuntime(): Promise<RuntimeInstallResult> {
  if (!isTauri()) return createPreviewRuntimeInstallResult();
  // This is a native, atomic side effect. The frontend never times it out or
  // retries it; the command itself owns locking, rollback, and verification.
  return parseRuntimeInstallResult(await invoke<unknown>("desktop_install_runtime"));
}

export async function reconcileDesktopRuntimeInstall(): Promise<RuntimeInstallReconciliation> {
  if (!isTauri()) {
    return { schema: "simplicio.desktop-install-reconciliation/v1", status: "clear", current: false, redacted: true };
  }
  return parseRuntimeInstallReconciliation(await invoke<unknown>("desktop_reconcile_runtime_install"));
}

export async function loadDesktopRuntimeInstallStatus(): Promise<RuntimeInstallStatus> {
  if (!isTauri()) {
    return { schema: "simplicio.desktop-install-status/v1", status: "clear", redacted: true };
  }
  return parseRuntimeInstallStatus(await invoke<unknown>("desktop_runtime_install_status"));
}

export async function beginDesktopLogin(): Promise<DesktopSnapshot> {
  if (!isTauri()) return createDemoSnapshot("active");
  // Runtime owns OAuth expiry; a frontend timeout must not authorize a duplicate login.
  return invoke<DesktopSnapshot>("desktop_login");
}

export async function logoutDesktop(): Promise<DesktopSnapshot> {
  if (!isTauri()) return createDemoSnapshot("signed_out");
  return invoke<DesktopSnapshot>("desktop_logout");
}

export async function refreshDesktopSnapshot(): Promise<DesktopSnapshot> {
  if (!isTauri()) return createDemoSnapshot(previewState());
  return readSnapshot(() => invoke<DesktopSnapshot>("refresh_desktop_snapshot"));
}

export async function planDesktopIntegrations(): Promise<IntegrationPlan> {
  if (!isTauri()) return createPreviewIntegrationPlan();
  return parseIntegrationPlan(await withTimeout(invoke<unknown>("desktop_plan_integrations"), 60_000, "integration_plan_timeout"));
}

export async function loadDesktopTokenReport(request: TokenQuery): Promise<TokenUsageReport> {
  if (!isTauri()) throw new Error("preview_no_runtime");
  return parseTokenUsageReport(await withTimeout(invoke<unknown>("desktop_token_report", { request }), 60_000, "token_report_timeout"));
}

export async function exportDesktopTokenReport(reportHash: string, format: "json" | "csv") {
  if (!isTauri()) throw new Error("preview_no_runtime");
  // Native state owns the report and destination. Never send a file body or path over IPC.
  return parseTokenExportReceipt(await invoke<unknown>("desktop_export_token_report", { reportHash, format }));
}

export async function applyDesktopHostPlugins(planDigest: string): Promise<HostPluginOperationResult> {
  if (!isTauri()) return createPreviewHostPluginResult(planDigest);
  // A side effect is never timed out or replayed by the frontend.
  return parseHostPluginOperationResult(await invoke<unknown>("desktop_apply_host_plugins", { planDigest }), "apply");
}

export async function reconcileDesktopHostPlugins(receiptId: string): Promise<HostPluginOperationResult> {
  if (!isTauri()) return createPreviewHostPluginResult(receiptId, "reconcile");
  // Reconciliation is an explicit Runtime operation, never part of snapshot refresh.
  return parseHostPluginOperationResult(await invoke<unknown>("desktop_reconcile_host_plugins", { receiptId }), "reconcile");
}

export async function dispatchDesktopBotAction(
  request: BotActionRequest,
  current: BotCenterSnapshot,
): Promise<BotCenterSnapshot> {
  if (!isTauri()) return applyDemoBotAction(current, request);
  return invoke<BotCenterSnapshot>("desktop_bot_action", { request });
}

export async function openDesktopSubscription(): Promise<void> {
  if (!isTauri()) {
    window.open("https://simpleti.com.br/simplicio", "_blank", "noopener,noreferrer");
    return;
  }
  await invoke("desktop_open_subscription");
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, message: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(message)), timeoutMs);
    promise.then(
      (value) => {
        window.clearTimeout(timer);
        resolve(value);
      },
      (error: unknown) => {
        window.clearTimeout(timer);
        reject(error);
      },
    );
  });
}
