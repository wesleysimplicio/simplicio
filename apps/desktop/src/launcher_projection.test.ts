import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createLauncherProjection } from "./launcher_projection";

describe("desktop.launcher/v1", () => {
  it("keeps common actions discoverable by stable capability IDs", () => {
    const projection = createLauncherProjection(createDemoSnapshot("active"));
    expect(projection.schema).toBe("desktop.launcher/v1");
    expect(projection.actions.map((action) => action.id)).toEqual(["chat.new", "team.new", "work.new", "app.open", "automation.new"]);
    expect(projection.actions.every((action) => action.available === false)).toBe(true);
  });

  it("does not treat Runtime health as proof of an action descriptor", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    const projection = createLauncherProjection(snapshot);
    expect(projection.actions.every((action) => action.available === false)).toBe(true);
    expect(projection.actions.every((action) => action.reasonCode === "action_descriptor_unavailable")).toBe(true);
    expect(projection.reasonCode).toBe("desktop.launcher_unavailable");
  });
});
