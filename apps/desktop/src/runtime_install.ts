export interface RuntimeInstallResult {
  schema: "simplicio.desktop-runtime-install/v1";
  status: "installed" | "already_current";
  scope: "runtime_core";
  source: "packaged_sidecar";
  installed: true;
  current: true;
  validated: true;
  backupAvailable: boolean;
  pluginsMutated: false;
  runtime: {
    state: "healthy";
    version: string;
  };
}

export interface RuntimeInstallReconciliation {
  schema: "simplicio.desktop-install-reconciliation/v1";
  status: "clear" | "reconciled";
  current: boolean;
  redacted: true;
}

export interface RuntimeInstallStatus {
  schema: "simplicio.desktop-install-status/v1";
  status: "clear" | "pending";
  redacted: true;
}

const SEMVER = /^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$/;

function validVersion(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 64) return false;
  const match = SEMVER.exec(value);
  return match !== null && (match[4] === undefined || match[4].split(".").every((identifier) =>
    !/^[0-9]+$/.test(identifier) || identifier === "0" || !identifier.startsWith("0")));
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("runtime_install_result_invalid");
  }
  return value as Record<string, unknown>;
}

/**
 * Projects the native receipt onto the small public contract used by the UI.
 * Extra native fields are deliberately discarded so paths, raw output, config,
 * backups, and credentials cannot become renderable frontend state.
 */
export function parseRuntimeInstallResult(value: unknown): RuntimeInstallResult {
  const result = record(value);
  const runtime = record(result.runtime);
  if (
    result.schema !== "simplicio.desktop-runtime-install/v1"
    || (result.status !== "installed" && result.status !== "already_current")
    || result.scope !== "runtime_core"
    || result.source !== "packaged_sidecar"
    || result.installed !== true
    || result.current !== true
    || result.validated !== true
    || typeof result.backupAvailable !== "boolean"
    || result.pluginsMutated !== false
    || runtime.state !== "healthy"
    || !validVersion(runtime.version)
  ) {
    throw new Error("runtime_install_result_invalid");
  }

  return {
    schema: "simplicio.desktop-runtime-install/v1",
    status: result.status,
    scope: "runtime_core",
    source: "packaged_sidecar",
    installed: true,
    current: true,
    validated: true,
    backupAvailable: result.backupAvailable,
    pluginsMutated: false,
    runtime: {
      state: runtime.state,
      version: runtime.version,
    },
  };
}

export function createPreviewRuntimeInstallResult(): RuntimeInstallResult {
  return {
    schema: "simplicio.desktop-runtime-install/v1",
    status: "already_current",
    scope: "runtime_core",
    source: "packaged_sidecar",
    installed: true,
    current: true,
    validated: true,
    backupAvailable: false,
    pluginsMutated: false,
    runtime: { state: "healthy", version: "0.0.0-preview" },
  };
}

export function parseRuntimeInstallReconciliation(value: unknown): RuntimeInstallReconciliation {
  const result = record(value);
  if (
    result.schema !== "simplicio.desktop-install-reconciliation/v1"
    || (result.status !== "clear" && result.status !== "reconciled")
    || typeof result.current !== "boolean"
    || result.redacted !== true
  ) {
    throw new Error("runtime_install_reconciliation_invalid");
  }
  return {
    schema: "simplicio.desktop-install-reconciliation/v1",
    status: result.status,
    current: result.current,
    redacted: true,
  };
}

export function parseRuntimeInstallStatus(value: unknown): RuntimeInstallStatus {
  const result = record(value);
  if (
    result.schema !== "simplicio.desktop-install-status/v1"
    || (result.status !== "clear" && result.status !== "pending")
    || result.redacted !== true
  ) {
    throw new Error("runtime_install_status_invalid");
  }
  return {
    schema: "simplicio.desktop-install-status/v1",
    status: result.status,
    redacted: true,
  };
}
