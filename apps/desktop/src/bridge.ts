import { invoke } from "@tauri-apps/api/core";
import type { AccessState, DesktopSnapshot } from "./contracts";
import { createDemoSnapshot } from "./demo";
import type { BotCenterSnapshot } from "./contracts";
import type { BotActionRequest } from "./bot_center";
import { applyDemoBotAction } from "./bot_center";
import { parseTokenExportReceipt, parseTokenUsageReport, type TokenQuery, type TokenUsageReport } from "./token_usage";
import { parseIntegrationPlan, type IntegrationPlan } from "./integration_setup";

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

  return invoke<DesktopSnapshot>("desktop_snapshot");
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
  return invoke<DesktopSnapshot>("refresh_desktop_snapshot");
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
