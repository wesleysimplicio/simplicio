import { describe, expect, it } from "vitest";
import { createCapabilityRegistry } from "./capability_registry";
import { createDemoSnapshot } from "./demo";

describe("capability.registry/v1", () => {
  it("keeps the five human capability categories stable", () => {
    const registry = createCapabilityRegistry(createDemoSnapshot("active"));
    expect(registry.schema).toBe("capability.registry/v1");
    expect(registry.capabilities.map((item) => item.category)).toEqual(["Create", "Explore", "Act", "Build", "Learn"]);
    expect(registry.capabilities.every((item) => item.available === false)).toBe(true);
  });

  it("does not substitute Runtime health for a capability probe or dispatch contract", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    expect(createCapabilityRegistry(snapshot).capabilities.every((item) => !item.available)).toBe(true);
    expect(createCapabilityRegistry(snapshot).capabilities.every((item) => item.reasonCode !== "capability_probe_verified")).toBe(true);
  });
});
