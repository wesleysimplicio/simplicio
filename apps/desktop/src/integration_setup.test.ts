import { describe, expect, it } from "vitest";
import { parseIntegrationPlan } from "./integration_setup";

describe("Desktop installation review", () => {
  const plan = { schema: "simplicio.desktop-integration-plan/v1", source: "runtime", planDigest: `sha256:${"a".repeat(64)}`, changes: [{ label: "codex", changed: true, exists: true, path: "/private", diff: "secret" }] };
  it("exposes only the bounded plan summary and confirmation digest", () => {
    const result = parseIntegrationPlan(plan);
    expect(result.changes[0]).toEqual({ label: "codex", changed: true, exists: true });
    expect(JSON.stringify(result)).not.toContain("secret");
  });
  it("rejects an absent digest and arbitrary config labels", () => {
    expect(() => parseIntegrationPlan({ ...plan, planDigest: "" })).toThrow();
    expect(() => parseIntegrationPlan({ ...plan, changes: [{ label: "/private", changed: true, exists: true }] })).toThrow();
  });
});
