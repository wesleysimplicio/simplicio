import { afterEach, describe, expect, it, vi } from "vitest";
import { collectReportPaths, consolidatedRange, createConsolidatedReader, parseConsolidatedReport, type ConsolidatedQuery } from "./consolidated_tokens";

afterEach(() => vi.useRealTimers());

const hash = `sha256:${"a".repeat(64)}`;
const query: ConsolidatedQuery = { repoPaths: ["/projects/a", "/projects/b"], fromEpoch: 10, toEpoch: 20, timezoneOffsetSeconds: 0 };
function fixture() {
  const totals = { sample_count: 2, input_tokens: 10, cached_input_tokens: 3, output_tokens: 4, reasoning_tokens: 1, paid_remote_tokens: 15, total_tokens: 15, missing_usage_events: 1, receipt_count: 2 };
  return { schema: "simplicio.desktop-consolidated-tokens/v1", source: "runtime", ...query, generatedAtEpoch: 21,
    projects: query.repoPaths.map((path, i) => ({ id: `project-${i}`, path, name: path, status: "ready", totals: { ...totals }, reportHash: hash })),
    totals: Object.fromEntries(Object.entries(totals).map(([key, value]) => [key, value * 2])), reportHash: hash };
}

describe("consolidated report", () => {
  it("does not duplicate a pending native batch after a timeout", async () => {
    vi.useFakeTimers();
    let complete!: (value: unknown) => void;
    const invoke = vi.fn(() => new Promise(resolve => { complete = resolve; }));
    const read = createConsolidatedReader(invoke, 20);
    const first = read(query);
    const failure = expect(first).rejects.toThrow("consolidated_report_timeout");
    await vi.advanceTimersByTimeAsync(21); await failure;
    expect(read(query)).toBe(first);
    await expect(read({ ...query, toEpoch: 30 })).rejects.toThrow("consolidated_report_busy");
    expect(invoke).toHaveBeenCalledTimes(1);
    complete(fixture()); await vi.advanceTimersByTimeAsync(0);
    const next = read(query); await vi.advanceTimersByTimeAsync(0);
    complete(fixture()); await expect(next).resolves.toMatchObject({ totals: { total_tokens: 30 } });
    expect(invoke).toHaveBeenCalledTimes(2);
  });
  it("uses exact rolling days, not calendar month for 30 days", () => {
    const now = new Date(2026, 7, 31, 12);
    expect(consolidatedRange("7d", now).toEpoch - consolidatedRange("7d", now).fromEpoch).toBe(7 * 86400);
    expect(consolidatedRange("30d", now).toEpoch - consolidatedRange("30d", now).fromEpoch).toBe(30 * 86400);
  });
  it("clamps calendar months and handles leap years", () => {
    expect(new Date(consolidatedRange("6m", new Date(2026, 7, 31, 12)).fromEpoch * 1000).getDate()).toBe(28);
    expect(new Date(consolidatedRange("6m", new Date(2024, 7, 31, 12)).fromEpoch * 1000).getDate()).toBe(29);
    expect(new Date(consolidatedRange("12m", new Date(2024, 1, 29, 12)).fromEpoch * 1000).getDate()).toBe(28);
    expect(new Date(consolidatedRange("3m", new Date(2026, 0, 31, 12)).fromEpoch * 1000).getMonth()).toBe(9);
    expect(() => consolidatedRange("7d", new Date(NaN))).toThrow();
  });
  it("merges discovered/bookmarked paths and bounds the batch", () => {
    const result = collectReportPaths(["/a", "/a", "relative", "//network/share", "/a\0", "C:\\projects\\a"]);
    expect(result.paths).toEqual(["/a", "C:\\projects\\a"]);
    expect(collectReportPaths(Array.from({ length: 100 }, (_, i) => `/p/${i}`)).omitted).toBe(4);
  });
  it("validates the exact interval and checked native sum, strips unknown fields", () => {
    const parsed = parseConsolidatedReport({ ...fixture(), prompts: "private" }, query);
    expect(parsed.totals?.total_tokens).toBe(30);
    expect(parsed).not.toHaveProperty("prompts");
    for (const field of ["fromEpoch", "toEpoch", "timezoneOffsetSeconds"]) expect(() => parseConsolidatedReport({ ...fixture(), [field]: 999 }, query)).toThrow();
    const bad = fixture(); bad.totals.input_tokens++;
    expect(() => parseConsolidatedReport(bad, query)).toThrow();
  });
  it("rejects missing, duplicated or unrequested project responses", () => {
    const short = fixture(); short.projects.pop();
    expect(() => parseConsolidatedReport(short, query)).toThrow();
    const duplicate = fixture(); duplicate.projects[1] = duplicate.projects[0];
    expect(() => parseConsolidatedReport(duplicate, query)).toThrow();
    const wrong = fixture(); wrong.projects[0].path = "/elsewhere";
    expect(() => parseConsolidatedReport(wrong, query)).toThrow();
  });
  it("accepts unknown coverage without interpreting it as zero", () => {
    const base = fixture();
    const projects = base.projects.map(p => ({ ...p, status: "missing", totals: null, reportHash: null }));
    expect(parseConsolidatedReport({ ...base, projects, totals: null }, query).totals).toBeNull();
    expect(() => parseConsolidatedReport({ ...base, projects }, query)).toThrow();
  });
  it("excludes duplicate ledgers from totals and rejects unsafe numbers", () => {
    const base = fixture();
    const projects = [base.projects[0], { ...base.projects[1], status: "duplicate", totals: null, reportHash: null }];
    expect(parseConsolidatedReport({ ...base, projects, totals: base.projects[0].totals }, query).totals?.total_tokens).toBe(15);
    const bad = fixture(); bad.projects[0].totals.input_tokens = Number.MAX_SAFE_INTEGER + 1;
    expect(() => parseConsolidatedReport(bad, query)).toThrow();
    expect(() => parseConsolidatedReport({ ...base, reportHash: "fake" }, query)).toThrow();
  });
});
