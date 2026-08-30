import type { BotCenterSnapshot, DesktopSnapshot } from "./contracts";

export type RoomMode = "Discuss" | "Execute" | "Review";

export interface RoomProjection {
  schema: "room/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  roomId: string | null;
  displayName: string | null;
  members: string[];
  modes: RoomMode[];
  activeMode: RoomMode | null;
  modeChangeAvailable: boolean;
  reasonCode: string;
}

export function createRoomProjection(snapshot: DesktopSnapshot, botCenter: BotCenterSnapshot, generatedAt = snapshot.generatedAt): RoomProjection {
  const room = botCenter.rooms[0];
  const live = snapshot.source === "runtime" && snapshot.runtime.state === "healthy";
  return {
    schema: "room/v1",
    generatedAt,
    source: snapshot.source,
    roomId: room?.roomId ?? null,
    displayName: room?.displayName ?? null,
    members: room?.members.map((member) => member.label) ?? [],
    modes: ["Discuss", "Execute", "Review"],
    activeMode: room ? "Discuss" : null,
    modeChangeAvailable: false,
    reasonCode: live ? "room.mode_action_descriptor_unavailable" : "room.projection_unavailable",
  };
}
