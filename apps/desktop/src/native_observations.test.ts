import { describe, expect, it } from "vitest";
import { parsePermissions, permissionIds } from "./system_permissions";
import { parseQuotas } from "./components/ProviderUsage";
describe("native permission and quota projections", () => {
  it("accepts OS observations without turning unknown permissions into denied", () => {
    const rows = permissionIds.map(id => ({ id, status: "unknown", canOpenSettings: true }));
    expect(parsePermissions({ schema: "simplicio.desktop-permissions/v1", source: "operating_system", rows })[0].status).toBe("unknown");
    expect(() => parsePermissions({ schema: "simplicio.desktop-permissions/v1", source: "operating_system", rows: [...rows.slice(1), rows[1]] })).toThrow();
  });
  it("requires a redacted provider record with source, scope, timestamp and windows", () => {
    const quota = { schema: "simplicio.provider-quotas/v2", status: "available", observedAt: 1900000000, providers: [{ id: "codex", source: "codex_app_server", accountScope: "local_authenticated_account", observedAt: 1900000000, redacted: true, status: "fresh", windows: [{ usedPercent: 21, windowDurationMins: 10080, resetsAt: 1900000000 }] }] };
    expect(parseQuotas(quota).providers[0].windows[0].usedPercent).toBe(21);
    quota.providers[0].windows[0].usedPercent = 101;
    expect(() => parseQuotas(quota)).toThrow();
    quota.providers[0].windows[0].usedPercent = 21;
    quota.providers[0].redacted = false;
    expect(() => parseQuotas(quota)).toThrow();
  });
  it("keeps stale and unavailable states explicit", () => {
    const stale = { schema: "simplicio.provider-quotas/v2", status: "stale", observedAt: 1900000000, providers: [{ id: "grok", source: "grok_cli_billing", accountScope: "local_cli_session", observedAt: 1899990000, redacted: true, status: "stale", error: "stale", windows: [{ usedPercent: 10, windowDurationMins: 43200, resetsAt: 1900000000 }] }] };
    expect(parseQuotas(stale).providers[0].status).toBe("stale");
    expect(parseQuotas({ ...stale, status: "unavailable", providers: [{ ...stale.providers[0], status: "unavailable", windows: [], error: "login_required" }] }).providers[0].windows).toHaveLength(0);
  });
  it("rejects mismatched source, future observations and unbounded windows", () => {
    const quota = { schema: "simplicio.provider-quotas/v2", status: "available", observedAt: 1900000000, providers: [{ id: "codex", source: "grok_cli_billing", accountScope: "local_authenticated_account", observedAt: 1900000001, redacted: true, status: "fresh", windows: [{ usedPercent: 21, windowDurationMins: 10080, resetsAt: 1900000000 }] }] };
    expect(() => parseQuotas(quota)).toThrow();
    quota.providers[0].source = "codex_app_server";
    quota.providers[0].observedAt = 1900000000;
    quota.providers[0].windows[0].windowDurationMins = 366 * 24 * 60 + 1;
    expect(() => parseQuotas(quota)).toThrow();
  });
  it("requires root status to agree with provider states", () => {
    const quota = { schema: "simplicio.provider-quotas/v2", status: "unavailable", observedAt: 1900000000, providers: [{ id: "codex", source: "codex_app_server", accountScope: "local_authenticated_account", observedAt: 1900000000, redacted: true, status: "fresh", windows: [{ usedPercent: 21, windowDurationMins: 10080, resetsAt: 1900000000 }] }] };
    expect(() => parseQuotas(quota)).toThrow();
  });
});
