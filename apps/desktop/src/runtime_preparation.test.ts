import { describe, expect, it } from "vitest";
import { parsePreparationPlan } from "./runtime_preparation";

const plan = () => ({
  schema: "simplicio.desktop-preparation-plan/v1", status: "planned",
  configurationWrites: 4, effectsApplied: false, memoryReady: false, requiresApply: true,
  python: { status: "detected", version: "3.13.2", dependenciesVerified: false },
});
describe("pre-login preparation boundary", () => {
  it("keeps planning separate from readiness and strips sensitive extras", () => {
    const result = parsePreparationPlan({ ...plan(), path: "/private/home", token: "SECRET",
      python: { ...plan().python, executable: "/private/python" } });
    expect(result.memoryReady).toBe(false);
    expect(result.effectsApplied).toBe(false);
    expect(result.python.dependenciesVerified).toBe(false);
    expect(JSON.stringify(result)).not.toMatch(/SECRET|private/);
  });
  it.each(["effectsApplied", "memoryReady"])("rejects invented readiness: %s", key => {
    expect(() => parsePreparationPlan({ ...plan(), [key]: true })).toThrow("preparation_plan_invalid");
  });
  it.each([-1, 65, 1.5, "4", null])("rejects invalid write counts %s", configurationWrites => {
    expect(() => parsePreparationPlan({ ...plan(), configurationWrites })).toThrow();
  });
  it("requires a bounded Python observation, not dependency success", () => {
    for (const python of [
      { status: "detected", version: "3x13x2", dependenciesVerified: false },
      { status: "detected", dependenciesVerified: false },
      { status: "detected", version: "3.13.2", dependenciesVerified: true },
      { status: "ready", dependenciesVerified: false },
    ]) expect(() => parsePreparationPlan({ ...plan(), python })).toThrow();
    expect(parsePreparationPlan({ ...plan(), python: { status: "not_detected", dependenciesVerified: false } }).python.status).toBe("not_detected");
  });
});
