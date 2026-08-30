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

  it("requires a Runtime probe before enabling a launcher action", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    expect(createLauncherProjection(snapshot).actions.every((action) => action.available)).toBe(true);
  });
});
