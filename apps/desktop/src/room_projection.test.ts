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

  it("keeps Execute and Review under Runtime authority", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    expect(createRoomProjection(snapshot, createDemoBotCenter()).modeChangeAvailable).toBe(true);
  });
});
