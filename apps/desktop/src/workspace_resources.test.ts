import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createWorkspaceResourcesProjection } from "./workspace_resources";

describe("workspace.resources/v1", () => {
  it("uses handles and never grants arbitrary filesystem access", () => {
    const projection = createWorkspaceResourcesProjection(createDemoSnapshot("active"));
    expect(projection.schema).toBe("workspace.resources/v1");
    expect(projection.arbitraryFilesystemAccess).toBe(false);
    expect(projection.resources.every((resource) => resource.pathHandle?.includes("://"))).toBe(true);
    expect(projection.resources.some((resource) => resource.writable)).toBe(false);
  });
});
