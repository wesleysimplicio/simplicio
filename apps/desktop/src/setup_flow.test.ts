import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { canConfigureRuntime, runtimeIsValid, setupStages, type SetupPhase } from "./setup_flow";

describe("guided setup evidence", () => {
  it("counts only operations that returned, never time-based progress", () => {
    const expected = { welcome: 0, checking: 0, planning: 1, review: 2, installing: 2, reconciling: 3, complete: 4 };
    for (const [phase, completed] of Object.entries(expected)) {
      expect(setupStages(phase as SetupPhase).filter((step) => step.state === "complete")).toHaveLength(completed);
    }
    expect(setupStages("review").map((step) => step.state)).toEqual(["complete", "complete", "pending", "pending"]);
    expect(setupStages("installing")[2].state).toBe("running");
  });

  it("keeps partial installation failures and failed verification distinct", () => {
    expect(setupStages("failed", 3).map((step) => step.state)).toEqual(["complete", "complete", "failed", "pending"]);
    expect(setupStages("failed", 4).map((step) => step.state)).toEqual(["complete", "complete", "complete", "failed"]);
  });

  it("requires known active access and a reachable Runtime", () => {
    const snapshot = createDemoSnapshot("active");
    expect(canConfigureRuntime(snapshot)).toBe(true);
    for (const state of ["signed_out", "unknown", "inactive"] as const) expect(canConfigureRuntime({ ...snapshot, access: { ...snapshot.access, state } })).toBe(false);
    expect(canConfigureRuntime({ ...snapshot, access: { ...snapshot.access, entitlementKnown: false } })).toBe(false);
    expect(canConfigureRuntime({ ...snapshot, runtime: { ...snapshot.runtime, state: "offline" } })).toBe(false);
    expect(canConfigureRuntime({ ...snapshot, runtime: { ...snapshot.runtime, transport: "unavailable" } })).toBe(false);
  });

  it("uses only a reachable healthy Runtime to skip core installation", () => {
    const snapshot = createDemoSnapshot("signed_out");
    expect(runtimeIsValid(snapshot)).toBe(true);
    expect(runtimeIsValid({ ...snapshot, runtime: { ...snapshot.runtime, state: "degraded" } })).toBe(false);
    expect(runtimeIsValid({ ...snapshot, runtime: { ...snapshot.runtime, state: "starting" } })).toBe(false);
    expect(runtimeIsValid({ ...snapshot, runtime: { ...snapshot.runtime, state: "offline" } })).toBe(false);
    expect(runtimeIsValid({ ...snapshot, runtime: { ...snapshot.runtime, transport: "unavailable" } })).toBe(false);
  });
});
