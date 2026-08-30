import { describe, expect, it } from "vitest";
import { createDemoBotCenter } from "./bot_center";
import { createDemoSnapshot } from "./demo";
import { createWorkspaceProjection } from "./workspace_projection";

describe("workspace/v1", () => {
  it("keeps Space, Team, Room and shared memory identity linked", () => {
    const snapshot = createDemoSnapshot("active");
    const projection = createWorkspaceProjection(snapshot, createDemoBotCenter());
    expect(projection.schema).toBe("workspace/v1");
    expect(projection.spaces[0].teamIds).toContain("team-desktop");
    expect(projection.teams[0].roomIds).toContain("room-desktop");
    expect(projection.teams[0].sharedMemoryScope).toBe("space-personal/team-desktop");
  });

  it("does not present preview membership as a live Workspace", () => {
    const snapshot = createDemoSnapshot("active");
    expect(createWorkspaceProjection(snapshot, createDemoBotCenter()).reasonCode).toBe("workspace.projection_unavailable");
  });
});
