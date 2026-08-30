import { describe, expect, it } from "vitest";
import { createAmbientProjection } from "./ambient";
import { createDemoSnapshot } from "./demo";

describe("ambient.state/v1", () => {
  it("keeps quiet as a valid non-animated state", () => {
    const projection = createAmbientProjection(createDemoSnapshot("active"));
    expect(projection.schema).toBe("ambient.state/v1");
    expect(projection.state).toBe("quiet");
    expect(projection.pulse).toBe(false);
  });

  it("surfaces attention and unavailable Runtime states without inventing work", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.activity[0].status = "attention";
    expect(createAmbientProjection(snapshot).state).toBe("attention");
    snapshot.runtime.state = "offline";
    expect(createAmbientProjection(snapshot).state).toBe("unavailable");
  });
});
