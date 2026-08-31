import { afterEach, describe, expect, it, vi } from "vitest";
import { contextErrorMessage, createContextReader, parseContextReport } from "./context_report";

function fixture(): Record<string, unknown> {
  return {
    schema: "simplicio.desktop-context-report/v1", source: "runtime", scope: "project_history",
    eventCount: 12, ledgerEventCount: 12, llmSpendEventCount: 0, savedTokens: 350,
    baselineTokens: 1000, actualTokens: 650, netTokens: 350,
    baselineKind: "mixed", confidence: "low", heuristicEventCount: 10, unlabeledEstimateCount: 1,
    proof: { measured: 9, estimated: 3, replayed: 0, benchmark: 0, unavailable: 0 },
    reportHash: `sha256:${"c".repeat(64)}`,
  };
}

afterEach(() => { vi.useRealTimers(); });

describe("bounded context report", () => {
  it("projects only metrics, not raw records or arbitrary extension fields", () => {
    const report = parseContextReport({ ...fixture(), records: ["secret"], cost: 99, source_artifacts: ["/private"] });
    expect(report.savedTokens).toBe(350);
    expect(report.netTokens).toBe(350);
    expect(report.proof.estimated).toBe(3);
    expect(JSON.stringify(report)).not.toMatch(/secret|source_artifacts|cost/);
  });

  it("preserves a negative net instead of using the gross savings as the net result", () => {
    const report = parseContextReport({ ...fixture(), actualTokens: 1100, netTokens: -100 });
    expect(report.netTokens).toBe(-100);
    expect(report.savedTokens).toBe(350);
  });

  it("requires unknown comparisons when the history contains LLM spending", () => {
    const raw = { ...fixture(), eventCount: 10, llmSpendEventCount: 2 };
    expect(() => parseContextReport(raw)).toThrow("context_report_invalid");
    expect(parseContextReport({ ...raw, baselineTokens: null, actualTokens: null, netTokens: null }).netTokens).toBeNull();
  });

  it.each([
    { source: "preview" }, { schema: "other" }, { savedTokens: Number.MAX_SAFE_INTEGER + 1 },
    { savedTokens: -1 }, { eventCount: 13 }, { ledgerEventCount: 0 }, { netTokens: 349 },
    { heuristicEventCount: 12 }, { confidence: "guaranteed" }, { baselineKind: "anything" },
    { proof: { measured: 10, estimated: 3, replayed: 0, benchmark: 0, unavailable: 0 } },
    { reportHash: "not-a-digest" },
  ])("rejects invalid data %j", (patch) => {
    expect(() => parseContextReport({ ...fixture(), ...patch })).toThrow("context_report_invalid");
  });

  it("shares same-project reads and rejects different scopes while a native call is outstanding", async () => {
    let complete!: (value: unknown) => void;
    const invoke = vi.fn(() => new Promise<unknown>((resolve) => { complete = resolve; }));
    const read = createContextReader(invoke);
    const first = read(" /tmp/project ");
    expect(read("/tmp/project")).toBe(first);
    await expect(read("/tmp/other")).rejects.toThrow("context_report_busy");
    expect(invoke).toHaveBeenCalledTimes(1);
    complete(fixture());
    await expect(first).resolves.toMatchObject({ savedTokens: 350 });
  });

  it("retains the project lock after observer timeout until the native operation actually settles", async () => {
    vi.useFakeTimers();
    let complete!: (value: unknown) => void;
    const invoke = vi.fn(() => new Promise<unknown>((resolve) => { complete = resolve; }));
    const read = createContextReader(invoke, 20);
    const first = read("/tmp/a");
    const failure = expect(first).rejects.toThrow("context_report_timeout");
    await vi.advanceTimersByTimeAsync(21);
    await failure;
    expect(read("/tmp/a")).toBe(first);
    await expect(read("/tmp/b")).rejects.toThrow("context_report_busy");
    expect(invoke).toHaveBeenCalledTimes(1);
    complete(fixture());
    await vi.advanceTimersByTimeAsync(0);
    const second = read("/tmp/b");
    await vi.advanceTimersByTimeAsync(0);
    expect(invoke).toHaveBeenCalledTimes(2);
    complete(fixture());
    await expect(second).resolves.toMatchObject({ savedTokens: 350 });
  });

  it("does not leak unknown native errors or turn unavailable evidence into savings", () => {
    expect(contextErrorMessage("context_ledger_invalid")).toContain("integridade");
    expect(contextErrorMessage("secret token: private")).not.toContain("secret");
    expect(contextErrorMessage("context_ledger_empty")).toContain("não significa consumo zero");
  });
});
