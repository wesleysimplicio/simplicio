import { invoke } from "@tauri-apps/api/core";
import type { AccessState, DesktopSnapshot } from "./contracts";
import { createDemoSnapshot } from "./demo";

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
  return invoke<DesktopSnapshot>("desktop_login");
}

export async function refreshDesktopSnapshot(): Promise<DesktopSnapshot> {
  if (!isTauri()) return createDemoSnapshot(previewState());
  return invoke<DesktopSnapshot>("refresh_desktop_snapshot");
}

export async function openDesktopSubscription(): Promise<void> {
  if (!isTauri()) {
    window.open("https://simpleti.com.br/simplicio", "_blank", "noopener,noreferrer");
    return;
  }
  await invoke("desktop_open_subscription");
}
