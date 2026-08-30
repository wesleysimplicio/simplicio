import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createSettingsProjection } from "./settings_projection";

describe("settings.projection/v1", () => {
  it("keeps providers and registries separate from secret bodies", () => {
    const projection = createSettingsProjection(createDemoSnapshot("active"));
    expect(projection.schema).toBe("settings.projection/v1");
    expect(projection.providers.length).toBeGreaterThan(0);
    expect(projection.secretPolicy).toEqual({ bodiesVisible: false, writeOnly: true, rawExport: false });
    expect(JSON.stringify(projection)).not.toContain("voce@example.com");
  });

  it("requires Runtime authority for model/tool/skill enablement", () => {
    const snapshot = createDemoSnapshot("active");
    expect(createSettingsProjection(snapshot).models[0].selectable).toBe(false);
    snapshot.source = "runtime";
    expect(createSettingsProjection(snapshot).models[0].selectable).toBe(true);
  });
});
