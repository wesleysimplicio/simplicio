import { describe, expect, it, vi } from "vitest";
import { buildUnifiedUsageQuery } from "../unified_usage";
import type { TokenPeriod, TokenUsageReport } from "../token_usage";
import { applyTokenScreenPeriodTransition } from "./TokensScreen";

const totals = {
  sample_count: 1,
  input_tokens: 10,
  cached_input_tokens: 0,
  output_tokens: 5,
  reasoning_tokens: 0,
  paid_remote_tokens: 15,
  total_tokens: 15,
  missing_usage_events: 0,
  receipt_count: 1,
};

describe("TokensScreen period integration", () => {
  it("does not reuse a loaded 7d range after the user switches to 1m", () => {
    const loaded: TokenUsageReport = {
      schema: "workspace.token-analytics-report/v1",
      now_epoch: 1_700_000_000,
      session_id: null,
      timezone_offset_seconds: 0,
      periods: [{ window: "7d", from_epoch: 111, to_epoch: 222, totals }],
      generated_by: "sqlite_ledger",
      report_hash: `sha256:${"a".repeat(64)}`,
    };

    let screen: { period: TokenPeriod; report: TokenUsageReport | null } = {
      period: "7d",
      report: loaded,
    };
    const invalidate = vi.fn();
    applyTokenScreenPeriodTransition("1m", {
      invalidate,
      setPeriod: (period) => { screen = { ...screen, period }; },
      setReport: (report) => { screen = { ...screen, report }; },
    });
    const selected = screen.report?.periods.find((item) => item.window === screen.period);
    const query = buildUnifiedUsageQuery({
      period: screen.period,
      now_epoch: 1_700_000_000,
      selected_range: selected,
    });

    expect(invalidate).toHaveBeenCalledOnce();
    expect(screen.report).toBeNull();
    expect(query).toEqual({
      from_epoch: 1_697_408_000,
      to_epoch: 1_700_000_000,
    });
    expect(query).not.toEqual({ from_epoch: 111, to_epoch: 222 });
  });
});
