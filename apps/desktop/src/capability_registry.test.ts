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

  it("requires a healthy Runtime source before exposing an app", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    expect(createCapabilityRegistry(snapshot).capabilities.every((item) => item.available)).toBe(true);
  });
});
