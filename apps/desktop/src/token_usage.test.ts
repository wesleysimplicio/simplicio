import { describe, expect, it } from "vitest";
import { parseTokenUsageReport, parseTokenExportReceipt, tokenExportErrorMessage, tokenErrorMessage } from "./token_usage";

function fixture() {
  return {
    schema: "workspace.token-analytics-report/v1", generated_by: "sqlite_ledger", now_epoch: 100,
    session_id: null, timezone_offset_seconds: 0, report_hash: `sha256:${"a".repeat(64)}`,
    periods: [{ window: "today", from_epoch: 0, to_epoch: 101, totals: {
      sample_count: 2, input_tokens: 10, cached_input_tokens: 3, output_tokens: 4,
      reasoning_tokens: 1, paid_remote_tokens: 15, total_tokens: 15, missing_usage_events: 1, receipt_count: 2,
    } }],
  };
}

describe("Runtime token usage report", () => {
  it("validates the real ledger shape and strips unrelated content", () => {
    const report = parseTokenUsageReport({ ...fixture(), prompts: "private", path: "/private" });
    expect(report.periods[0].totals.total_tokens).toBe(15);
    expect(report).not.toHaveProperty("prompts");
    expect(report).not.toHaveProperty("path");
  });

  it("rejects wrong schemas, duplicate periods and unsafe or inconsistent totals", () => {
    const wrong = fixture(); wrong.schema = "insights.tokens/v1";
    expect(() => parseTokenUsageReport(wrong)).toThrow("token_report_invalid");
    const duplicate = fixture(); duplicate.periods.push(duplicate.periods[0]);
    expect(() => parseTokenUsageReport(duplicate)).toThrow();
    for (const value of [-1, Infinity, Number.MAX_SAFE_INTEGER + 1, 1.5, 11]) {
      const bad = fixture(); bad.periods[0].totals.cached_input_tokens = value;
      expect(() => parseTokenUsageReport(bad)).toThrow();
    }
    const bad = fixture(); bad.periods[0].totals.total_tokens = 999;
    expect(() => parseTokenUsageReport(bad)).toThrow();
  });

  it("accepts only confirmed native export receipts", () => {
    const receipt = { schema: "simplicio.desktop-token-export/v1", format: "json", path: "/Downloads/simplicio-token-usage.json", bytes: 500 };
    expect(parseTokenExportReceipt(receipt).path).toBe(receipt.path);
    for (const invalid of [null, {}, { ...receipt, schema: "other" }, { ...receipt, bytes: 0 }, { ...receipt, format: "sh" }]) {
      expect(() => parseTokenExportReceipt(invalid)).toThrow("token_export_unconfirmed");
    }
  });

  it("surfaces native export permission and stale report failures without false success", () => {
    expect(tokenExportErrorMessage("token_export_permission_denied")).toContain("nenhuma permissão foi alterada");
    expect(tokenExportErrorMessage("token_export_report_expired")).toContain("Consulte o uso novamente");
    expect(tokenExportErrorMessage("unknown failure")).toContain("Não foi possível confirmar");
  });

  it("does not treat a missing ledger as zero consumption", () => {
    expect(tokenErrorMessage("token_ledger_unavailable")).toContain("não significa consumo zero");
  });
});
