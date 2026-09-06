import { describe, expect, it } from "vitest";
import { parsePreparationResult } from "./runtime_preparation_result";

const ready = {
  schema: "simplicio.desktop-preparation-result/v1",
  status: "ready",
  effectsApplied: true,
  runtimeDependencies: { status: "ready", pythonRequired: false },
  python: { status: "detected", version: "3.13.2", dependenciesVerified: false },
  memory: { ready: true, items: 815, skills: 557, migrations: 16 },
  clients: { configured: 8, skipped: 4 },
  redacted: true,
};

describe("pre-login environment receipt", () => {
  it("accepts only bounded redacted readiness", () => {
    expect(parsePreparationResult({ ...ready, binary: "/private/user/bin", token: "secret" }))
      .toEqual(ready);
  });

  it("rejects incomplete memory and invented Python dependencies", () => {
    expect(() => parsePreparationResult({ ...ready, memory: { ...ready.memory, migrations: 0 } }))
      .toThrow("preparation_result_invalid");
    expect(() => parsePreparationResult({
      ...ready,
      python: { ...ready.python, dependenciesVerified: true },
    })).toThrow("preparation_result_invalid");
  });
});
