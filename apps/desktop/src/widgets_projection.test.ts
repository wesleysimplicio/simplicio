import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createWidgetsProjection } from "./widgets_projection";

describe("capability.widgets/v1", () => {
  it("keeps widgets opt-in, read-only and bounded", () => {
    const widgets = createWidgetsProjection(createDemoSnapshot("active"));
    expect(widgets.schema).toBe("capability.widgets/v1");
    expect(widgets.maxPinned).toBe(3);
    expect(widgets.widgets).toHaveLength(0);
    expect(widgets.writesAvailable).toBe(false);
  });
});
