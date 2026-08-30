import type { BotCenterSnapshot, DesktopSnapshot } from "./contracts";

export interface LiveTask {
  workItemId: string;
  sessionId: string;
  botId: string;
  state: "working" | "waiting" | "paused" | "blocked" | "completed";
}

export interface LiveProjection {
  schema: "live.mission-control/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  visible: boolean;
  tasks: LiveTask[];
  reasonCode: string;
}

export function createLiveProjection(snapshot: DesktopSnapshot, botCenter: BotCenterSnapshot, generatedAt = snapshot.generatedAt): LiveProjection {
  const tasks: LiveTask[] = botCenter.sessions.map((session) => ({
    workItemId: "WI-01",
    sessionId: session.sessionId,
    botId: session.botId,
    state: session.state === "running" ? "working" : session.state === "idle" ? "waiting" : session.state,
  }));
  const visible = tasks.some((task) => task.state === "working" || task.state === "waiting" || task.state === "paused" || task.state === "blocked");
  return {
    schema: "live.mission-control/v1",
    generatedAt,
    source: snapshot.source,
    visible,
    tasks,
    reasonCode: snapshot.source === "runtime" ? "live.mission_control_projection_ready" : "live.mission_control_projection_unavailable",
  };
}
