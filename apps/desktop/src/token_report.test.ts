import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createTokenReport } from "./token_report";

describe("insights.tokens/v1", () => {
  it("keeps measured/estimated evidence distinguishable", () => {
    const report = createTokenReport(createDemoSnapshot("active"));
    expect(report.schema).toBe("insights.tokens/v1");
    expect(report.savedTokens).toBe(1_842_610);
    expect(report.proofKind).toBe("mixed");
    expect(report.providerCacheHitPercent).toBeNull();
  });

  it("does not invent totals without proof", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.savings.proofKind = "unavailable";
    expect(createTokenReport(snapshot).savedTokens).toBeNull();
    expect(createTokenReport(snapshot).reasonCode).toBe("insights.tokens_telemetry_unavailable");
  });
});
