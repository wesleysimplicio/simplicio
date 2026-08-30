import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createTodayProjection } from "./today_projection";

describe("ambient.today/v1", () => {
  it("keeps the dashboard bounded and projection-first", () => {
    const projection = createTodayProjection(createDemoSnapshot("active"));
    expect(projection.schema).toBe("ambient.today/v1");
    expect(projection.limits).toEqual({ focus: 1, inProgress: 3, upNext: 3 });
    expect(projection.inProgress).toHaveLength(0);
    expect(projection.upNext.length).toBeLessThanOrEqual(3);
    expect(projection.reasonCode).toBe("ambient.today_projection_unavailable");
  });

  it("does not claim the Runtime projection without a Runtime source", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    expect(createTodayProjection(snapshot).reasonCode).toBe("ambient.today_projection_ready");
  });
});
