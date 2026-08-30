import type { DesktopSnapshot } from "./contracts";

export interface TokenReport {
  schema: "insights.tokens/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  savedTokens: number | null;
  estimatedUsd: number | null;
  providerCacheHitPercent: number | null;
  proofKind: DesktopSnapshot["savings"]["proofKind"];
  telemetrySource: string | null;
  reasonCode: string;
}

export function createTokenReport(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): TokenReport {
  const savings = snapshot.savings;
  const measured = savings.proofKind === "measured" || savings.proofKind === "mixed" || savings.proofKind === "replayed";
  return {
    schema: "insights.tokens/v1",
    generatedAt,
    source: snapshot.source,
    savedTokens: measured ? savings.monthTokens : null,
    estimatedUsd: measured ? savings.estimatedUsd : null,
    providerCacheHitPercent: savings.providerCache.proofKind === "measured" ? savings.providerCache.hitPercent : null,
    proofKind: savings.proofKind,
    telemetrySource: savings.providerCache.telemetrySource,
    reasonCode: measured ? "insights.tokens_projection_ready" : "insights.tokens_telemetry_unavailable",
  };
}
