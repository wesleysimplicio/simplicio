import type {
  BotActionKind,
  BotCenterSnapshot,
  BotSessionProjection,
  BotSummary,
  BotTimelineEvent,
  DesktopSnapshot,
} from "./contracts";

export interface BotActionRequest {
  kind: BotActionKind;
  botId: string;
  sessionId?: string | null;
  value?: string | null;
  approvalId?: string | null;
}

function digest(letter: string): string {
  return `sha256:${letter.repeat(64)}`;
}

function demoBot(bot: Omit<BotSummary, "lastActivityAt" | "lastSessionId">, generatedAt: string): BotSummary {
  return {
    ...bot,
    lastActivityAt: generatedAt,
    lastSessionId: `${bot.botId}-session-01`,
  };
}

function event(
  input: Pick<BotTimelineEvent, "eventId" | "kind" | "actorKind" | "actorId" | "actorLabel" | "content"> & Partial<BotTimelineEvent>,
): BotTimelineEvent {
  return {
    eventId: input.eventId,
    sessionId: input.sessionId ?? "bot-cora-session-01",
    botId: input.botId ?? "bot-cora",
    kind: input.kind,
    actorKind: input.actorKind,
    actorId: input.actorId,
    actorLabel: input.actorLabel,
    content: input.content,
    timestamp: input.timestamp ?? "2026-08-30T00:00:00.000Z",
    causalParentId: input.causalParentId ?? null,
    state: input.state ?? "complete",
    toolName: input.toolName,
    approvalId: input.approvalId,
    artifactName: input.artifactName,
    attachmentName: input.attachmentName,
    reasonCode: input.reasonCode,
  };
}

export function createUnavailableBotCenter(generatedAt = new Date().toISOString()): BotCenterSnapshot {
  return {
    schema: "simplicio.bot-center-snapshot/v1",
    generatedAt,
    source: "runtime",
    actionAuthority: "unavailable",
    bots: [],
    selectedBotId: null,
    sessions: [],
    rooms: [],
    computer: {
      available: false,
      computerSessionId: null,
      botId: null,
      sessionId: null,
      state: "blocked",
      leaseRevision: null,
      reasonCode: "agent_api_unavailable",
      lastEventAt: null,
    },
    limits: { maxBots: 32, maxEvents: 200, maxRooms: 32 },
    redaction: { secrets: true, prompts: true, attachmentBodies: true },
    snapshotDigest: digest("0"),
  };
}

export function createDemoBotCenter(generatedAt = new Date().toISOString()): BotCenterSnapshot {
  const bots: BotSummary[] = [
    demoBot({
      botId: "bot-cora",
      displayName: "Cora",
      agentProfileId: "profile-cora-dev",
      profileId: "profile-dev",
      projectId: "project-simplicio",
      provider: "OpenAI",
      model: "gpt-5.6",
      toolset: ["filesystem", "git", "tests"],
      skills: ["simplicio-mapper", "simplicio-loop"],
      lifecycle: "busy",
      reasonCode: "session_running",
      capabilities: [
        { id: "chat", label: "Chat streaming", available: true, reasonCode: "capability_verified" },
        { id: "tools", label: "Tools governadas", available: true, reasonCode: "capability_verified" },
        { id: "computer", label: "Computer Use", available: false, reasonCode: "computer_backend_unavailable" },
      ],
    }, generatedAt),
    demoBot({
      botId: "bot-iris",
      displayName: "Íris",
      agentProfileId: "profile-iris-review",
      profileId: "profile-review",
      projectId: null,
      provider: "OpenAI",
      model: "gpt-5.6",
      toolset: ["git", "diff"],
      skills: ["code-review"],
      lifecycle: "blocked",
      reasonCode: "provider_capability_unverified",
      capabilities: [
        { id: "chat", label: "Chat streaming", available: false, reasonCode: "provider_capability_unverified" },
        { id: "tools", label: "Tools governadas", available: false, reasonCode: "provider_capability_unverified" },
        { id: "computer", label: "Computer Use", available: false, reasonCode: "computer_backend_unavailable" },
      ],
    }, generatedAt),
  ];

  const sessionId = "bot-cora-session-01";
  const events: BotTimelineEvent[] = [
    event({ eventId: "evt-01", sessionId, botId: "bot-cora", kind: "status", actorKind: "runtime", actorId: "runtime", actorLabel: "Runtime", content: "Sessão aberta com revision 7.", timestamp: generatedAt, reasonCode: "session_started" }),
    event({ eventId: "evt-02", sessionId, botId: "bot-cora", kind: "message", actorKind: "human", actorId: "human", actorLabel: "Você", content: "Revise a integração do Desktop com os contratos do Runtime.", timestamp: generatedAt }),
    event({ eventId: "evt-03", sessionId, botId: "bot-cora", kind: "message", actorKind: "bot", actorId: "bot-cora", actorLabel: "Cora", content: "Vou verificar somente as projeções públicas e os reason codes disponíveis.", timestamp: generatedAt, causalParentId: "evt-02" }),
    event({ eventId: "evt-04", sessionId, botId: "bot-cora", kind: "tool_call", actorKind: "bot", actorId: "bot-cora", actorLabel: "Cora", content: "Solicitou leitura de capabilities do Runtime.", timestamp: generatedAt, causalParentId: "evt-03", toolName: "runtime.capabilities.list" }),
    event({ eventId: "evt-05", sessionId, botId: "bot-cora", kind: "tool_result", actorKind: "runtime", actorId: "runtime", actorLabel: "Runtime", content: "Capabilities retornadas sem secrets.", timestamp: generatedAt, causalParentId: "evt-04", toolName: "runtime.capabilities.list" }),
    event({ eventId: "evt-06", sessionId, botId: "bot-cora", kind: "approval_request", actorKind: "runtime", actorId: "runtime", actorLabel: "Runtime", content: "Aguardando aprovação para criar um branch de trabalho.", timestamp: generatedAt, causalParentId: "evt-05", approvalId: "approval-branch-01", state: "blocked", reasonCode: "approval_required" }),
    event({ eventId: "evt-07", sessionId, botId: "bot-cora", kind: "artifact", actorKind: "bot", actorId: "bot-cora", actorLabel: "Cora", content: "Plano de integração disponível como artifact.", timestamp: generatedAt, causalParentId: "evt-05", artifactName: "desktop-bot-mode-plan.md" }),
    event({ eventId: "evt-08", sessionId, botId: "bot-cora", kind: "attachment", actorKind: "human", actorId: "human", actorLabel: "Você", content: "Anexo referenciado por hash; corpo não é exposto no snapshot.", timestamp: generatedAt, causalParentId: "evt-02", attachmentName: "runtime-contracts.pdf" }),
    event({ eventId: "evt-09", sessionId, botId: "bot-cora", kind: "bot_event", actorKind: "bot", actorId: "bot-iris", actorLabel: "Íris", content: "@Cora: a capability de Computer Use ainda não está verificada.", timestamp: generatedAt, causalParentId: "evt-05", reasonCode: "cross_bot_event" }),
  ];

  const sessions: BotSessionProjection[] = [{
    sessionId,
    botId: "bot-cora",
    roomId: "room-desktop",
    state: "blocked",
    revision: 7,
    events,
    tokenUsage: { input: 2840, output: 618, cached: 1210, proofKind: "measured" },
    costUsd: 0.0184,
    cacheHitPercent: 42.6,
  }];

  return {
    schema: "simplicio.bot-center-snapshot/v1",
    generatedAt,
    source: "preview",
    actionAuthority: "preview",
    bots,
    selectedBotId: "bot-cora",
    sessions,
    rooms: [{
      roomId: "room-desktop",
      displayName: "Desktop · Bot Mode",
      members: [
        { id: "human", label: "Você", kind: "human", role: "owner" },
        { id: "bot-cora", label: "Cora", kind: "bot", role: "operator" },
        { id: "bot-iris", label: "Íris", kind: "bot", role: "reviewer" },
      ],
      sessionId,
      unread: 1,
    }],
    computer: {
      available: false,
      computerSessionId: null,
      botId: "bot-cora",
      sessionId,
      state: "blocked",
      leaseRevision: null,
      reasonCode: "computer_backend_unavailable",
      lastEventAt: generatedAt,
    },
    limits: { maxBots: 32, maxEvents: 200, maxRooms: 32 },
    redaction: { secrets: true, prompts: true, attachmentBodies: true },
    snapshotDigest: digest("c"),
  };
}

function sessionFor(snapshot: BotCenterSnapshot, request: BotActionRequest): BotSessionProjection | undefined {
  return snapshot.sessions.find((session) => session.sessionId === request.sessionId)
    ?? snapshot.sessions.find((session) => session.botId === request.botId);
}

export function applyDemoBotAction(snapshot: BotCenterSnapshot, request: BotActionRequest): BotCenterSnapshot {
  if (snapshot.actionAuthority !== "preview") return snapshot;
  const session = sessionFor(snapshot, request);
  if (!session || request.kind === "take_over" || request.kind === "hand_back") return snapshot;
  const now = new Date().toISOString();
  const labels: Record<Exclude<BotActionKind, "send_turn" | "take_over" | "hand_back">, string> = {
    interrupt: "Interrupção solicitada ao Runtime.",
    cancel: "Cancelamento solicitado ao Runtime.",
    steer: request.value ? `Steer enviado: ${request.value}` : "Steer enviado ao Runtime.",
    resume: "Retomada solicitada ao Runtime.",
    branch: "Branch solicitado ao Runtime; aguardando receipt.",
    handoff: "Handoff solicitado ao Runtime.",
    approve: "Aprovação enviada ao Runtime.",
    deny: "Negação enviada ao Runtime.",
  };
  const content = request.kind === "send_turn"
    ? request.value?.trim() || "Turn vazio ignorado."
    : labels[request.kind];
  const nextEvent = event({
    eventId: `evt-local-${Date.now()}`,
    sessionId: session.sessionId,
    botId: session.botId,
    kind: request.kind === "send_turn" ? "message" : request.kind === "approve" || request.kind === "deny" ? "approval_decision" : "status",
    actorKind: request.kind === "send_turn" ? "human" : "runtime",
    actorId: request.kind === "send_turn" ? "human" : "runtime",
    actorLabel: request.kind === "send_turn" ? "Você" : "Runtime",
    content,
    timestamp: now,
    causalParentId: session.events.at(-1)?.eventId ?? null,
    approvalId: request.approvalId,
    reasonCode: "preview_action",
  });
  const nextState = request.kind === "interrupt" || request.kind === "cancel" ? "paused" : request.kind === "resume" ? "running" : session.state;
  const nextSession: BotSessionProjection = { ...session, state: nextState, revision: session.revision + 1, events: [...session.events, nextEvent] };
  return {
    ...snapshot,
    generatedAt: now,
    sessions: snapshot.sessions.map((item) => item.sessionId === nextSession.sessionId ? nextSession : item),
    snapshotDigest: digest("d"),
  };
}

export function snapshotWithDemoBots(snapshot: DesktopSnapshot): BotCenterSnapshot {
  if (snapshot.botCenter) return snapshot.botCenter;
  return snapshot.source === "preview"
    ? createDemoBotCenter(snapshot.generatedAt)
    : createUnavailableBotCenter(snapshot.generatedAt);
}
