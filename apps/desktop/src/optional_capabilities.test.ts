import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createOptionalCapabilitiesProjection } from "./optional_capabilities";

describe("optional.capabilities/v1", () => {
  it("lists Voice, Computer, Learning and Insights without pretending they work", () => {
    const projection = createOptionalCapabilitiesProjection(createDemoSnapshot("active"));
    expect(projection.schema).toBe("optional.capabilities/v1");
    expect(projection.capabilities.map((capability) => capability.id)).toEqual(["voice", "computer", "learning", "insights"]);
    expect(projection.capabilities.every((capability) => capability.action === "unavailable")).toBe(true);
  });

  it("enables optional capabilities only after a Runtime projection", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    expect(createOptionalCapabilitiesProjection(snapshot).capabilities.every((capability) => capability.available)).toBe(true);
  });
});
