import type { DesktopSnapshot } from "./contracts";

export interface ReleaseProjection {
  schema: "desktop.release/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  channel: "stable" | "beta";
  platforms: Array<{ id: "macos" | "windows" | "linux"; supported: boolean; artifact: string | null; checksum: string | null }>;
  updater: { available: boolean; rollback: boolean; provenanceRequired: true; reasonCode: string };
  reasonCode: string;
}

export function createReleaseProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): ReleaseProjection {
  const live = snapshot.source === "runtime" && snapshot.runtime.state === "healthy";
  return {
    schema: "desktop.release/v1",
    generatedAt,
    source: snapshot.source,
    channel: "stable",
    platforms: (["macos", "windows", "linux"] as const).map((id) => ({ id, supported: live, artifact: null, checksum: null })),
    updater: { available: live, rollback: live, provenanceRequired: true, reasonCode: live ? "desktop.release_verified" : "desktop.release_unavailable" },
    reasonCode: live ? "desktop.release_projection_ready" : "desktop.release_projection_unavailable",
  };
}
