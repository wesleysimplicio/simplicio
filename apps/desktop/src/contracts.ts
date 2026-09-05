import type { DesktopHostPlugins } from "./integration_setup";

export type AccessState = "signed_out" | "inactive" | "active" | "unknown";

export type ProviderState =
  | "connected"
  | "registered"
  | "detected"
  | "needs_attention"
  | "not_installed";

export type ProviderTier = "first_class" | "compatible";

export interface ProductAccess {
  state: AccessState;
  identityKnown: boolean;
  entitlementKnown: boolean;
  reasonCode: string;
  checkedAt: string;
  expiresAt: string | null;
  displayName: string | null;
  email: string | null;
  plan: string | null;
}

export interface RuntimeStatus {
  state: "healthy" | "starting" | "degraded" | "offline";
  version: string;
  transport: "sidecar" | "daemon" | "unavailable";
  lastReceiptAt: string | null;
  deterministic: {
    ready: boolean;
    cpuFirst: boolean;
    mapper: "canonical" | "legacy" | "unknown";
    mapCache: "generation_scoped" | "legacy" | "unknown";
    hookContext: "receipt_only" | "legacy" | "unknown";
  };
  optionalFast: {
    required: boolean;
    hookInjected: boolean;
    status: "not_required" | "injected" | "unknown";
  };
}

export interface ProviderConnection {
  id: string;
  name: string;
  kind: "agent" | "editor";
  protocol: "MCP" | "Plugin" | "CLI";
  tier: ProviderTier;
  state: ProviderState;
  detail: string;
  installState: "installed" | "absent";
  registrationState: "registered" | "unregistered";
  handshakeState: "live" | "stale" | "unverified";
  freshness: "current" | "stale" | "unknown";
  reasonCode: string;
  availableActions: Array<"register" | "verify" | "repair">;
}

export interface SavingsSummary {
  monthTokens: number;
  monthPercent: number;
  estimatedUsd: number | null;
  proofKind: "measured" | "estimated" | "replayed" | "mixed" | "unavailable";
  ledgerStatus: "valid" | "unavailable";
  eventCount: number;
  providerCache: {
    status: "hit" | "miss" | "mixed" | "unknown";
    hitPercent: number | null;
    proofKind: "measured" | "unavailable";
    telemetrySource: string | null;
  };
  decisionCache: {
    hitPercent: number | null;
    runs: number;
    proofKind: "measured" | "unavailable";
    hits: number;
  };
  mapCache: {
    status: "ready" | "warming" | "invalid" | "unavailable";
    delivery: "receipt_only";
    generation: string | null;
    digest: string | null;
    bytes: number | null;
    fastInHooks: false;
  };
}

export interface ActivityItem {
  id: string;
  title: string;
  detail: string;
  provider: string;
  savedTokens: number;
  occurredAt: string;
  status: "verified" | "running" | "attention";
}

export type BotLifecycle = "disabled" | "idle" | "active" | "busy" | "degraded" | "blocked";
export type BotControlState = "bot_control" | "human_control" | "paused" | "blocked";
export type BotActionKind =
  | "send_turn"
  | "interrupt"
  | "cancel"
  | "steer"
  | "resume"
  | "branch"
  | "handoff"
  | "approve"
  | "deny"
  | "take_over"
  | "hand_back";

export interface BotCapability {
  id: string;
  label: string;
  available: boolean;
  reasonCode: string;
}

export interface BotSummary {
  botId: string;
  displayName: string;
  agentProfileId: string;
  profileId: string;
  projectId: string | null;
  provider: string | null;
  model: string | null;
  toolset: string[];
  skills: string[];
  lifecycle: BotLifecycle;
  reasonCode: string;
  lastSessionId: string | null;
  lastActivityAt: string | null;
  capabilities: BotCapability[];
}

export type BotEventKind =
  | "message"
  | "tool_call"
  | "tool_result"
  | "approval_request"
  | "approval_decision"
  | "artifact"
  | "attachment"
  | "status"
  | "bot_event";

export interface BotTimelineEvent {
  eventId: string;
  sessionId: string;
  botId: string;
  kind: BotEventKind;
  actorKind: "human" | "bot" | "runtime";
  actorId: string;
  actorLabel: string;
  content: string;
  timestamp: string;
  causalParentId: string | null;
  state: "streaming" | "complete" | "blocked";
  toolName?: string | null;
  approvalId?: string | null;
  artifactName?: string | null;
  attachmentName?: string | null;
  reasonCode?: string | null;
}

export interface BotSessionProjection {
  sessionId: string;
  botId: string;
  roomId: string | null;
  state: "idle" | "running" | "paused" | "blocked" | "completed";
  revision: number;
  events: BotTimelineEvent[];
  tokenUsage: {
    input: number | null;
    output: number | null;
    cached: number | null;
    proofKind: "measured" | "unavailable";
  };
  costUsd: number | null;
  cacheHitPercent: number | null;
}

export interface BotRoomProjection {
  roomId: string;
  displayName: string;
  members: Array<{ id: string; label: string; kind: "human" | "bot"; role: string }>;
  sessionId: string | null;
  unread: number;
}

export interface ComputerProjection {
  available: boolean;
  computerSessionId: string | null;
  botId: string | null;
  sessionId: string | null;
  state: BotControlState;
  leaseRevision: number | null;
  reasonCode: string;
  lastEventAt: string | null;
}

export interface BotCenterSnapshot {
  schema: "simplicio.bot-center-snapshot/v1";
  generatedAt: string;
  source: "runtime" | "preview";
  actionAuthority: "runtime" | "preview" | "unavailable";
  bots: BotSummary[];
  selectedBotId: string | null;
  sessions: BotSessionProjection[];
  rooms: BotRoomProjection[];
  computer: ComputerProjection;
  limits: {
    maxBots: 32;
    maxEvents: 200;
    maxRooms: 32;
  };
  redaction: {
    secrets: true;
    prompts: true;
    attachmentBodies: true;
  };
  snapshotDigest: string;
}

export interface DesktopSnapshot {
  schema: "simplicio.desktop-snapshot/v1";
  generatedAt: string;
  source: "runtime" | "preview";
  access: ProductAccess;
  runtime: RuntimeStatus;
  savings: SavingsSummary;
  providers: ProviderConnection[];
  /** Latest Runtime-owned host-plugin receipt projection; reading it never verifies or reconciles. */
  hostPlugins?: DesktopHostPlugins;
  activity: ActivityItem[];
  botCenter?: BotCenterSnapshot;
  actions: Array<{
    id: "login" | "subscribe" | "refresh_access" | "repair_providers";
    governed: true;
    executed: false;
  }>;
  freshness: {
    access: string;
    runtime: string;
    savings: string;
    providers: string;
  };
  redaction: {
    personalPaths: true;
    configurationBodies: true;
    credentials: true;
    prompts: true;
    skillBodies: true;
    rawLedgers: true;
  };
  limits: {
    maxBytes: 65536;
    maxProviders: 32;
    maxActivity: 5;
  };
  snapshotDigest: string;
}
