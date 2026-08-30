import { describe, expect, it } from "vitest";
import { createDemoBotCenter } from "./bot_center";
import { createDemoSnapshot } from "./demo";
import { createLibraryProjection } from "./library_projection";

describe("library.artifacts/v1", () => {
  it("keeps artifact handles, versions and provenance linked to a session", () => {
    const library = createLibraryProjection(createDemoSnapshot("active"), createDemoBotCenter());
    expect(library.schema).toBe("library.artifacts/v1");
    expect(library.artifacts[0]).toMatchObject({ name: "desktop-bot-mode-plan.md", version: "v1", provenance: "bot-cora-session-01" });
    expect(library.artifacts[0].handle).toBe("artifact://desktop-bot-mode-plan.md");
  });

  it("keeps the unavailable source explicit", () => {
    expect(createLibraryProjection(createDemoSnapshot("active"), createDemoBotCenter()).reasonCode).toBe("library.artifacts_projection_unavailable");
  });
});
