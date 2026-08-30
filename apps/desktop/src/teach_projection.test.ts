import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createTeachProjection } from "./teach_projection";

describe("teach.recorder/v1", () => {
  it("requires explicit consent and redacts secret steps", () => {
    const projection = createTeachProjection(createDemoSnapshot("active"));
    expect(projection.schema).toBe("teach.recorder/v1");
    expect(projection.recordingScope).toBe("explicit_steps_only");
    expect(projection.consentRequired).toBe(true);
    expect(projection.steps.find((step) => step.kind === "secret")?.redacted).toBe(true);
    expect(projection.actions.saveDraft).toBe(false);
  });
});
