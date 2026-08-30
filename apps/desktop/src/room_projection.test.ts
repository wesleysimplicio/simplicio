import { describe, expect, it } from "vitest";
import { createDemoBotCenter } from "./bot_center";
import { createDemoSnapshot } from "./demo";
import { createRoomProjection } from "./room_projection";

describe("room/v1", () => {
  it("exposes the three explicit room modes", () => {
    const room = createRoomProjection(createDemoSnapshot("active"), createDemoBotCenter());
    expect(room.schema).toBe("room/v1");
    expect(room.roomId).toBe("room-desktop");
    expect(room.modes).toEqual(["Discuss", "Execute", "Review"]);
    expect(room.activeMode).toBe("Discuss");
    expect(room.modeChangeAvailable).toBe(false);
  });

  it("does not enable mode changes without a verified action descriptor", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    const room = createRoomProjection(snapshot, createDemoBotCenter());
    expect(room.modeChangeAvailable).toBe(false);
    expect(room.reasonCode).toBe("room.mode_action_descriptor_unavailable");
  });
});
