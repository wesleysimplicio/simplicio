import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createReleaseProjection } from "./release_projection";

describe("desktop.release/v1", () => {
  it("requires checksums and provenance for all target platforms", () => {
    const release = createReleaseProjection(createDemoSnapshot("active"));
    expect(release.schema).toBe("desktop.release/v1");
    expect(release.platforms.map((platform) => platform.id)).toEqual(["macos", "windows", "linux"]);
    expect(release.updater.provenanceRequired).toBe(true);
    expect(release.updater.available).toBe(false);
  });
});
