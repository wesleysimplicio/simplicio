import { invoke } from "@tauri-apps/api/core";
import type { AccessState, DesktopSnapshot } from "./contracts";
import { createDemoSnapshot } from "./demo";
import type { BotCenterSnapshot } from "./contracts";
import type { BotActionRequest } from "./bot_center";
import { applyDemoBotAction } from "./bot_center";

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
  return withTimeout(invoke<DesktopSnapshot>("desktop_login"), 120_000, "Tempo limite do login excedido.");
}

export async function logoutDesktop(): Promise<DesktopSnapshot> {
  if (!isTauri()) return createDemoSnapshot("signed_out");
  return invoke<DesktopSnapshot>("desktop_logout");
}

export async function refreshDesktopSnapshot(): Promise<DesktopSnapshot> {
  if (!isTauri()) return createDemoSnapshot(previewState());
  return invoke<DesktopSnapshot>("refresh_desktop_snapshot");
}

export async function repairDesktopProviders(): Promise<DesktopSnapshot> {
  if (!isTauri()) return createDemoSnapshot(previewState());
  return withTimeout(
    invoke<DesktopSnapshot>("desktop_repair_providers"),
    120_000,
    "Tempo limite do reparo de integrações excedido.",
  );
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
