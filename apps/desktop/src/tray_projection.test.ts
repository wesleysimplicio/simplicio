import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createTrayProjection } from "./tray_projection";

describe("desktop.tray/v1", () => {
  it("shows only attention and never keeps Runtime alive by itself", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.activity[0].status = "attention";
    const tray = createTrayProjection(snapshot);
    expect(tray.schema).toBe("desktop.tray/v1");
    expect(tray.visible).toBe(true);
    expect(tray.unreadAttentionCount).toBe(1);
    expect(tray.keepsRuntimeAlive).toBe(false);
  });
});
