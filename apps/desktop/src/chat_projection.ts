import type { BotCenterSnapshot, BotTimelineEvent } from "./contracts";

export interface ChatProjection {
  schema: "chat.session/v1";
  generatedAt: string;
  source: BotCenterSnapshot["source"];
  sessionId: string | null;
  state: "idle" | "running" | "paused" | "blocked" | "completed" | "unavailable";
  revision: number | null;
  events: BotTimelineEvent[];
  actions: { send: boolean; interrupt: boolean; cancel: boolean; steer: boolean };
  redaction: { prompts: true; attachmentBodies: true; secrets: true };
  reasonCode: string;
}

export function createChatProjection(botCenter: BotCenterSnapshot, generatedAt = botCenter.generatedAt): ChatProjection {
  const session = botCenter.sessions[0];
  const live = botCenter.actionAuthority === "runtime";
  return {
    schema: "chat.session/v1",
    generatedAt,
    source: botCenter.source,
    sessionId: session?.sessionId ?? null,
    state: session?.state ?? "unavailable",
    revision: session?.revision ?? null,
    events: session?.events ?? [],
    actions: { send: live, interrupt: live, cancel: live, steer: live },
    redaction: { prompts: true, attachmentBodies: true, secrets: true },
    reasonCode: live ? "chat.session_projection_ready" : "agent_api_unavailable",
  };
}
