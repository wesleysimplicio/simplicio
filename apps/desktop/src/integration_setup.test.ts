import { describe, expect, it } from "vitest";
import { integrationChangeLabel, integrationTargetsVerified, parseIntegrationPlan, type IntegrationPlan } from "./integration_setup";

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
  it("rejects duplicate target labels before a plan can be reviewed or applied", () => {
    for (const duplicate of [plan.changes[0], { label: "codex", changed: false, exists: false }]) {
      expect(() => parseIntegrationPlan({ ...plan, changes: [...plan.changes, duplicate] })).toThrow("integration_plan_ambiguous_targets");
    }
  });
  it.each([
    { exists: true, changed: true, expected: "Atualizar" },
    { exists: false, changed: true, expected: "Criar" },
    { exists: true, changed: false, expected: "Já configurado" },
    { exists: false, changed: false, expected: "Configuração ausente" },
  ])("labels exists=$exists changed=$changed without assuming configuration", ({ exists, changed, expected }) => {
    expect(integrationChangeLabel({ label: "codex", exists, changed })).toBe(expected);
  });
});

describe("post-apply configuration verification", () => {
  const reviewed: IntegrationPlan = {
    schema: "simplicio.desktop-integration-plan/v1", source: "runtime", planDigest: `sha256:${"a".repeat(64)}`,
    changes: [{ label: "codex", changed: true, exists: true }, { label: "hermes", changed: true, exists: false }, { label: "stable", changed: false, exists: true }],
  };
  function observed(overrides: Partial<IntegrationPlan> = {}): IntegrationPlan {
    return { ...reviewed, planDigest: `sha256:${"b".repeat(64)}`, changes: reviewed.changes.map((row) => ({ ...row, exists: true, changed: false })), ...overrides };
  }

  it("requires changed targets to exist with no pending changes after application", () => {
    expect(integrationTargetsVerified(reviewed, observed())).toBe(true);
    expect(integrationTargetsVerified(reviewed, reviewed)).toBe(false);
  });

  it("matches exact labels rather than order or the old plan digest", () => {
    const current = observed();
    current.changes.reverse();
    expect(current.planDigest).not.toBe(reviewed.planDigest);
    expect(integrationTargetsVerified(reviewed, current)).toBe(true);
  });

  it("does not expand the reviewed scope to newly discovered targets", () => {
    const current = observed();
    current.changes.push({ label: "new-client", changed: true, exists: false });
    expect(integrationTargetsVerified(reviewed, current)).toBe(true);
  });

  it("rejects disappeared, absent and still-changing reviewed targets", () => {
    for (const changes of [
      observed().changes.filter((row) => row.label !== "codex"),
      observed().changes.map((row) => row.label === "codex" ? { ...row, exists: false } : row),
      observed().changes.map((row) => row.label === "codex" ? { ...row, changed: true } : row),
    ]) expect(integrationTargetsVerified(reviewed, observed({ changes }))).toBe(false);
  });

  it("rejects duplicated labels in either plan instead of selecting a convenient match", () => {
    const duplicateReview = { ...reviewed, changes: [...reviewed.changes, { label: "codex", changed: false, exists: true }] };
    const duplicateObservation = observed();
    duplicateObservation.changes.push({ label: "codex", changed: true, exists: true });
    expect(integrationTargetsVerified(duplicateReview, observed())).toBe(false);
    expect(integrationTargetsVerified(reviewed, duplicateObservation)).toBe(false);
  });

  it("rejects drift in a plan made entirely of already configured targets", () => {
    const unchanged = { ...reviewed, changes: [{ label: "stable", exists: true, changed: false }] };
    for (const changes of [[], [{ label: "stable", exists: false, changed: false }], [{ label: "stable", exists: true, changed: true }]]) {
      expect(integrationTargetsVerified(unchanged, observed({ changes }))).toBe(false);
    }
    expect(integrationTargetsVerified(unchanged, observed({ changes: unchanged.changes }))).toBe(true);
  });

  it("rejects drift in a preexisting target even when every modified target is clean", () => {
    for (const changes of [
      observed().changes.filter((row) => row.label !== "stable"),
      observed().changes.map((row) => row.label === "stable" ? { ...row, exists: false } : row),
      observed().changes.map((row) => row.label === "stable" ? { ...row, changed: true } : row),
    ]) expect(integrationTargetsVerified(reviewed, observed({ changes }))).toBe(false);
  });

  it("never uses a preview plan to confirm runtime configuration", () => {
    expect(integrationTargetsVerified(reviewed, observed({ source: "preview" }))).toBe(false);
    const previewReview = { ...reviewed, source: "preview" as const };
    expect(integrationTargetsVerified(previewReview, previewReview)).toBe(false);
    expect(integrationTargetsVerified(previewReview, observed({ source: "preview" }))).toBe(true);
  });

  it("allows an empty reviewed change set without making handshake claims", () => {
    const unchanged = { ...reviewed, changes: reviewed.changes.map((row) => ({ ...row, changed: false })) };
    expect(integrationTargetsVerified(unchanged, observed())).toBe(true);
    expect(integrationTargetsVerified({ ...reviewed, changes: [] }, observed({ changes: [] }))).toBe(true);
  });

  it("does not mutate either plan while checking configuration evidence", () => {
    const current = observed();
    const before = JSON.stringify([reviewed, current]);
    integrationTargetsVerified(reviewed, current);
    expect(JSON.stringify([reviewed, current])).toBe(before);
  });
});
