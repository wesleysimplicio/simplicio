import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createFlagshipProjection } from "./flagship_projection";

describe("flagship.apps/v1", () => {
  it("keeps first-party Apps on one capability request/output contract", () => {
    const projection = createFlagshipProjection(createDemoSnapshot("active"));
    expect(projection.schema).toBe("flagship.apps/v1");
    expect(projection.requestSchema).toBe("capability.request/v1");
    expect(projection.apps.map((app) => app.id)).toEqual(["video", "browser", "computer", "research", "files_pdf", "code_build"]);
    expect(projection.sharedOutputs).toContain("artifact");
    expect(projection.apps.every((app) => app.available === false)).toBe(true);
  });
});
