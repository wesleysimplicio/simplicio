import type { BotCenterSnapshot } from "./contracts";

export interface ChatSessionSummary {
  sessionId: string;
  botId: string;
  title: string;
  state: "idle" | "running" | "paused" | "blocked" | "completed";
  revision: number;
  unread: number;
}

export interface MultiChatProjection {
  schema: "chat.workspace/v1";
  generatedAt: string;
  source: BotCenterSnapshot["source"];
  selectedSessionId: string | null;
  sessions: ChatSessionSummary[];
  reasonCode: string;
}

export function createMultiChatProjection(botCenter: BotCenterSnapshot, generatedAt = botCenter.generatedAt): MultiChatProjection {
  const sessions = botCenter.sessions.map((session) => ({
    sessionId: session.sessionId,
    botId: session.botId,
    title: botCenter.bots.find((bot) => bot.botId === session.botId)?.displayName ?? session.botId,
    state: session.state,
    revision: session.revision,
    unread: session.events.filter((event) => event.actorKind === "bot" && event.state === "complete").length,
  }));
  return {
    schema: "chat.workspace/v1",
    generatedAt,
    source: botCenter.source,
    selectedSessionId: sessions[0]?.sessionId ?? null,
    sessions,
    reasonCode: botCenter.actionAuthority === "runtime" ? "chat.workspace_projection_ready" : "chat.workspace_projection_unavailable",
  };
}
