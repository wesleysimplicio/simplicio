import { describe, expect, it } from "vitest";
import { createBriefingProjection } from "./briefing_projection";
import { createDemoSnapshot } from "./demo";

describe("ambient.briefing/v1", () => {
  it("keeps a briefing bounded and delivery opt-in", () => {
    const briefing = createBriefingProjection(createDemoSnapshot("active"));
    expect(briefing.schema).toBe("ambient.briefing/v1");
    expect(briefing.items.length).toBeLessThanOrEqual(3);
    expect(briefing.schedule.configured).toBe(false);
    expect(briefing.delivery.configured).toBe(false);
    expect(briefing.delivery.target).toBeNull();
  });
});
