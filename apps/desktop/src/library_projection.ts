import type { BotCenterSnapshot, DesktopSnapshot } from "./contracts";

export interface LibraryArtifact {
  artifactId: string;
  name: string;
  kind: "document" | "diff" | "image" | "file";
  version: string;
  source: "runtime" | "preview";
  provenance: string;
  handle: string;
}

export interface LibraryProjection {
  schema: "library.artifacts/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  artifacts: LibraryArtifact[];
  reasonCode: string;
}

export function createLibraryProjection(snapshot: DesktopSnapshot, botCenter: BotCenterSnapshot, generatedAt = snapshot.generatedAt): LibraryProjection {
  const artifactNames = botCenter.sessions.flatMap((session) => session.events.filter((event) => event.kind === "artifact").map((event) => event.artifactName).filter((name): name is string => Boolean(name)));
  const unique = [...new Set(artifactNames)];
  return {
    schema: "library.artifacts/v1",
    generatedAt,
    source: snapshot.source,
    artifacts: unique.map((name, index) => ({
      artifactId: `artifact-${index + 1}`,
      name,
      kind: name.endsWith(".md") ? "document" : "file",
      version: "v1",
      source: snapshot.source,
      provenance: botCenter.sessions[0]?.sessionId ?? "unknown-session",
      handle: `artifact://${name}`,
    })),
    reasonCode: snapshot.source === "runtime" ? "library.artifacts_projection_ready" : "library.artifacts_projection_unavailable",
  };
}
