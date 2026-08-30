import { describe, expect, it } from "vitest";
import { createDemoBotCenter } from "./bot_center";
import { createDemoSnapshot } from "./demo";
import { createLiveProjection } from "./live_projection";

describe("live.mission-control/v1", () => {
  it("keeps Live contextual and linked to canonical sessions", () => {
    const snapshot = createDemoSnapshot("active");
    const projection = createLiveProjection(snapshot, createDemoBotCenter());
    expect(projection.schema).toBe("live.mission-control/v1");
    expect(projection.visible).toBe(true);
    expect(projection.tasks[0]).toMatchObject({ workItemId: "WI-01", sessionId: "bot-cora-session-01", botId: "bot-cora" });
    expect(projection.reasonCode).toBe("live.mission_control_projection_unavailable");
  });

  it("does not show a permanent Live affordance for completed work", () => {
    const snapshot = createDemoSnapshot("active");
    const bots = createDemoBotCenter();
    bots.sessions[0].state = "completed";
    expect(createLiveProjection(snapshot, bots).visible).toBe(false);
  });
});
