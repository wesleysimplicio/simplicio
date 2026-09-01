import { describe, expect, it } from "vitest";
import { parseRuntimeInstallResult } from "./runtime_install";

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
