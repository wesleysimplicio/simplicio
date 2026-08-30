import { describe, expect, it } from "vitest";
import { createDemoBotCenter } from "./bot_center";
import { createDemoSnapshot } from "./demo";
import { createWorkItemProjection } from "./work_item_projection";

describe("work.item/v1", () => {
  it("binds Work Item to Team, Room, Bot, Session and approval", () => {
    const snapshot = createDemoSnapshot("active");
    const item = createWorkItemProjection(snapshot, createDemoBotCenter());
    expect(item.schema).toBe("work.item/v1");
    expect(item.status).toBe("blocked");
    expect(item.teamId).toBe("team-desktop");
    expect(item.roomId).toBe("room-desktop");
    expect(item.sessionId).toBe("bot-cora-session-01");
    expect(item.approvalId).toBe("approval-branch-01");
    expect(item.action).toBe("unavailable");
  });

  it("never turns a preview Work Item into an executable action", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    expect(createWorkItemProjection(snapshot, createDemoBotCenter()).action).toBe("approve");
  });
});
