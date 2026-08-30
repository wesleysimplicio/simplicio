import { describe, expect, it } from "vitest";
import { createAmbientControlsProjection } from "./ambient_controls";
import { createDemoSnapshot } from "./demo";

describe("ambient.controls/v1", () => {
  it("defaults to Suggestions Only and keeps the mode list explicit", () => {
    const controls = createAmbientControlsProjection(createDemoSnapshot("active"));
    expect(controls.schema).toBe("ambient.controls/v1");
    expect(controls.mode).toBe("suggestions_only");
    expect(controls.availableModes).toHaveLength(4);
    expect(controls.emergencyStop.available).toBe(false);
    expect(controls.persistInRuntime).toBe(false);
  });
});
