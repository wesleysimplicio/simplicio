import { invoke } from "@tauri-apps/api/core";
import { open as openFolderDialog } from "@tauri-apps/plugin-dialog";
import type { AccessState, DesktopSnapshot } from "./contracts";
import { createDemoSnapshot } from "./demo";
import type { BotCenterSnapshot } from "./contracts";
import type { BotActionRequest } from "./bot_center";
import { applyDemoBotAction } from "./bot_center";
import { parseTokenExportReceipt, parseTokenUsageReport, type TokenQuery, type TokenUsageReport } from "./token_usage";
import { parseIntegrationPlan, type IntegrationPlan } from "./integration_setup";
import { parseLocalProject, type LocalProject } from "./workbench";
import { createReadonlyRequest } from "./readonly_request";
import { createContextReader } from "./context_report";
import { parseUsageProjects } from "./project_usage";
import { createConsolidatedReader, type ConsolidatedQuery, type ConsolidatedReport } from "./consolidated_tokens";

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
  if (!isTauri()) return { schema: "simplicio.desktop-integration-plan/v1", source: "preview", planDigest: `sha256:${"0".repeat(64)}`, changes: [{ label: "codex", exists: true, changed: false }, { label: "grok", exists: true, changed: true }] };
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

export async function repairDesktopProviders(planDigest: string): Promise<DesktopSnapshot> {
  if (!isTauri()) return createDemoSnapshot(previewState());
  // Do not release the UI mutation lock on a timer while the native installer may still run.
  return invoke<DesktopSnapshot>("desktop_repair_providers", { planDigest });
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
