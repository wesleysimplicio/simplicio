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
  displayName?: string;
  email?: string;
  plan?: string;
  renewsAt?: string;
}

export interface RuntimeStatus {
  state: "healthy" | "starting" | "degraded" | "offline";
  version?: string;
  transport: "sidecar" | "daemon" | "unavailable";
  lastReceiptAt?: string;
}

export interface ProviderConnection {
  id: string;
  name: string;
  kind: "agent" | "editor";
  protocol: "MCP" | "Plugin" | "CLI";
  tier: ProviderTier;
  state: ProviderState;
  detail: string;
  account?: string;
  version?: string;
}

export interface SavingsSummary {
  monthTokens: number;
  monthPercent: number;
  estimatedUsd: number;
  cacheHitPercent: number;
  deterministicRuns: number;
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
}
