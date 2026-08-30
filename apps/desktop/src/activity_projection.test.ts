import { describe, expect, it } from "vitest";
import { createActivityProjection } from "./activity_projection";
import { createDemoSnapshot } from "./demo";

describe("activity.center/v1", () => {
  it("keeps the center bounded and redacted", () => {
    const activity = createActivityProjection(createDemoSnapshot("active"));
    expect(activity.schema).toBe("activity.center/v1");
    expect(activity.items.length).toBeLessThanOrEqual(5);
    expect(activity.pageSize).toBe(5);
    expect(activity.exportHandle).toBeNull();
    expect(activity.redaction.rawLedgers).toBe(true);
  });
});
