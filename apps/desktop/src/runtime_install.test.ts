import { describe, expect, it } from "vitest";
import { parseRuntimeInstallReconciliation, parseRuntimeInstallResult, parseRuntimeInstallStatus } from "./runtime_install";

function validResult() {
  return {
    schema: "simplicio.desktop-runtime-install/v1",
    status: "installed",
    scope: "runtime_core",
    source: "packaged_sidecar",
    installed: true,
    current: true,
    validated: true,
    backupAvailable: true,
    pluginsMutated: false,
    runtime: { state: "healthy", version: "3.8.40" },
  };
}

describe("Runtime core installer receipt", () => {
  it("keeps only the sanitized native projection", () => {
    const parsed = parseRuntimeInstallResult({
      ...validResult(),
      path: "/Users/private/.simplicio/bin/simplicio",
      backupPath: "/Users/private/.simplicio/bin/simplicio.previous",
      rawOutput: "secret-token",
      runtime: { ...validResult().runtime, config: { token: "secret-token" } },
    });
    expect(parsed).toEqual(validResult());
    expect(JSON.stringify(parsed)).not.toMatch(/Users|backupPath|rawOutput|secret-token|config/);
  });

  it("fails closed when core installation or validation is not proven", () => {
    for (const invalid of [
      { ...validResult(), installed: false },
      { ...validResult(), current: false },
      { ...validResult(), validated: false },
      { ...validResult(), pluginsMutated: true },
      { ...validResult(), scope: "plugins" },
      { ...validResult(), runtime: { state: "degraded", version: "3.8.40" } },
      { ...validResult(), runtime: { state: "offline", version: "3.8.40" } },
      { ...validResult(), runtime: { state: "healthy", version: "/private/runtime" } },
      { ...validResult(), runtime: { state: "healthy", version: "3.8" } },
      { ...validResult(), runtime: { state: "healthy", version: "3.8.40-01" } },
    ]) {
      expect(() => parseRuntimeInstallResult(invalid)).toThrow("runtime_install_result_invalid");
    }
  });
});

describe("durable Runtime install reconciliation", () => {
  it("surfaces only whether a persisted attempt is pending", () => {
    expect(parseRuntimeInstallStatus({
      schema: "simplicio.desktop-install-status/v1",
      status: "pending",
      redacted: true,
      error: "runtime_install_timeout",
    })).toEqual({ schema: "simplicio.desktop-install-status/v1", status: "pending", redacted: true });
  });

  it("accepts only the closed redacted reconciliation projection", () => {
    expect(parseRuntimeInstallReconciliation({
      schema: "simplicio.desktop-install-reconciliation/v1",
      status: "reconciled",
      current: true,
      redacted: true,
      path: "/private/user/.simplicio/install-attempt.json",
    })).toEqual({
      schema: "simplicio.desktop-install-reconciliation/v1",
      status: "reconciled",
      current: true,
      redacted: true,
    });
  });

  it("fails closed on malformed or unredacted reconciliation", () => {
    expect(() => parseRuntimeInstallReconciliation({
      schema: "simplicio.desktop-install-reconciliation/v1",
      status: "reconciled",
      current: true,
      redacted: false,
    })).toThrow("runtime_install_reconciliation_invalid");
    expect(() => parseRuntimeInstallReconciliation({
      schema: "simplicio.desktop-install-reconciliation/v1",
      status: "pending",
      current: false,
      redacted: true,
    })).toThrow("runtime_install_reconciliation_invalid");
  });
});
