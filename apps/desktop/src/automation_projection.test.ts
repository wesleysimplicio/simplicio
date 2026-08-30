import { describe, expect, it } from "vitest";
import { createAutomationProjection } from "./automation_projection";
import { createDemoSnapshot } from "./demo";

describe("automation.studio/v1", () => {
  it("keeps suggestions review-only and sourced by receipt IDs", () => {
    const projection = createAutomationProjection(createDemoSnapshot("active"));
    expect(projection.schema).toBe("automation.studio/v1");
    expect(projection.suggestions).toHaveLength(2);
    expect(projection.suggestions.every((item) => item.state === "review_required")).toBe(true);
    expect(projection.draftAllowed).toBe(false);
    expect(projection.activeCount).toBeNull();
  });

  it("only permits a draft after a healthy Runtime projection", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    expect(createAutomationProjection(snapshot).draftAllowed).toBe(true);
  });
});
