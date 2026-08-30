import type { BotCenterSnapshot, DesktopSnapshot } from "./contracts";

export interface WorkItemProjection {
  schema: "work.item/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  workItemId: string;
  title: string;
  status: "queued" | "running" | "paused" | "blocked" | "completed" | "failed";
  teamId: string;
  roomId: string | null;
  botId: string | null;
  sessionId: string | null;
  approvalId: string | null;
  action: "open" | "approve" | "resume" | "unavailable";
  reasonCode: string;
}

export function createWorkItemProjection(snapshot: DesktopSnapshot, botCenter: BotCenterSnapshot, generatedAt = snapshot.generatedAt): WorkItemProjection {
  const session = botCenter.sessions[0];
  const approval = session?.events.find((event) => event.kind === "approval_request");
  const status = session?.state === "running" ? "running" : session?.state === "completed" ? "completed" : approval ? "blocked" : "queued";
  return {
    schema: "work.item/v1",
    generatedAt,
    source: snapshot.source,
    workItemId: "WI-01",
    title: "Revisar integração do Desktop",
    status,
    teamId: "team-desktop",
    roomId: session?.roomId ?? null,
    botId: session?.botId ?? null,
    sessionId: session?.sessionId ?? null,
    approvalId: approval?.approvalId ?? null,
    action: snapshot.source === "runtime" ? (approval ? "approve" : "open") : "unavailable",
    reasonCode: snapshot.source === "runtime" ? "work.item_projection_ready" : "work.item_projection_unavailable",
  };
}
