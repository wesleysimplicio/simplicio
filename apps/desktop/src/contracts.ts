export type AccessState = "signed_out" | "inactive" | "active" | "unknown";

export type ProviderState =
  | "connected"
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
    cpuFirst: true;
    mapper: "canonical";
    mapCache: "generation_scoped";
    hookContext: "receipt_only";
  };
  optionalFast: {
    required: false;
    hookInjected: false;
    status: "not_required";
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

export interface DesktopSnapshot {
  schema: "simplicio.desktop-snapshot/v1";
  generatedAt: string;
  source: "runtime" | "preview";
  access: ProductAccess;
  runtime: RuntimeStatus;
  savings: SavingsSummary;
  providers: ProviderConnection[];
  activity: ActivityItem[];
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
