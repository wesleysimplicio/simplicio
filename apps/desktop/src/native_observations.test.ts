import { describe, expect, it } from "vitest";
import { parsePermissions, permissionIds } from "./system_permissions";
import { parseQuotas } from "./components/ProviderUsage";
describe("native permission and quota projections", () => {
  it("accepts OS observations without turning unknown permissions into denied", () => {
    const rows = permissionIds.map(id => ({ id, status: "unknown", canOpenSettings: true }));
    expect(parsePermissions({ schema: "simplicio.desktop-permissions/v1", source: "operating_system", rows })[0].status).toBe("unknown");
    expect(() => parsePermissions({ schema: "simplicio.desktop-permissions/v1", source: "operating_system", rows: [...rows.slice(1), rows[1]] })).toThrow();
  });
  it("rejects quota percentages outside the contract", () => {
    const quota = { schema: "simplicio.provider-quotas/v1", status: "available", groups: [{ id: "codex", windows: [{ usedPercent: 21, windowDurationMins: 10080, resetsAt: 1900000000 }] }] };
    expect(parseQuotas(quota).groups[0].windows[0].usedPercent).toBe(21);
    quota.groups[0].windows[0].usedPercent = 101;
    expect(() => parseQuotas(quota)).toThrow();
  });
});
