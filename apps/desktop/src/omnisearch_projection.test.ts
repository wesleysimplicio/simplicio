import { describe, expect, it } from "vitest";
import { createDemoBotCenter } from "./bot_center";
import { createDemoSnapshot } from "./demo";
import { createOmniSearchProjection, searchOmni } from "./omnisearch_projection";

describe("search.omni/v1", () => {
  it("indexes navigable entities without secrets", () => {
    const projection = createOmniSearchProjection(createDemoSnapshot("active"), createDemoBotCenter());
    expect(projection.schema).toBe("search.omni/v1");
    expect(projection.entities.map((entity) => entity.kind)).toEqual(expect.arrayContaining(["capability", "session", "work_item", "artifact", "team"]));
    expect(projection.entities.every((entity) => entity.secretIndexed === false)).toBe(true);
    expect(projection.entities.some((entity) => entity.label === "voce@example.com")).toBe(false);
  });

  it("searches the same bounded index used by the UI", () => {
    const projection = createOmniSearchProjection(createDemoSnapshot("active"), createDemoBotCenter());
    expect(searchOmni(projection, "desktop").map((entity) => entity.id)).toEqual(expect.arrayContaining(["WI-01", "team-desktop", "desktop-bot-mode-plan.md"]));
  });
});
