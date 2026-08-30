import type { BotCenterSnapshot, DesktopSnapshot } from "./contracts";

export interface WorkspaceTeam {
  teamId: string;
  displayName: string;
  memberIds: string[];
  roomIds: string[];
  sharedMemoryScope: string;
}

export interface WorkspaceSpace {
  spaceId: string;
  displayName: string;
  teamIds: string[];
  active: boolean;
}

export interface WorkspaceProjection {
  schema: "workspace/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  spaces: WorkspaceSpace[];
  teams: WorkspaceTeam[];
  reasonCode: string;
}

export function createWorkspaceProjection(snapshot: DesktopSnapshot, botCenter: BotCenterSnapshot, generatedAt = snapshot.generatedAt): WorkspaceProjection {
  const room = botCenter.rooms[0];
  return {
    schema: "workspace/v1",
    generatedAt,
    source: snapshot.source,
    spaces: [{ spaceId: "space-personal", displayName: "Personal", teamIds: ["team-desktop"], active: true }],
    teams: [{
      teamId: "team-desktop",
      displayName: "Desktop",
      memberIds: room?.members.map((member) => member.id) ?? [],
      roomIds: room ? [room.roomId] : [],
      sharedMemoryScope: "space-personal/team-desktop",
    }],
    reasonCode: snapshot.source === "runtime" ? "workspace.projection_ready" : "workspace.projection_unavailable",
  };
}
