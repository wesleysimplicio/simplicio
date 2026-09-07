import { describe, expect, it } from "vitest";
import { createPreviewExecutionReport, parseExecutionReport } from "./execution_report";

describe("execution report contract", () => {
  it("keeps cache and included reasoning out of the exclusive total", () => {
    const report = parseExecutionReport({
      schema: "simplicio.execution-report/v1",
      owner: "simplicio-runtime",
      run_id: "run-5569",
      status: "COMPLETE",
      tasks: [{
        task_id: "task-1",
        title: "normalização",
        outcome: "COMPLETE",
        tokens: {
          tokens_in: 1_000,
          tokens_out: 200,
          tokens_cached: 800,
          cache_read_tokens: 800,          cache_write_tokens: 200,
          tokens_reasoning: 150,
          tokens_total: 1_200,
          input_semantics: "uncached_only",
          reasoning_semantics: "included_in_output",
          cost_microusd: null,
          cost_status: "unavailable",
          source: "provider-reported",
        },
        stages: [{
          stage_id: "verify",
          name: "Validação",
          status: "failed",
          wall_ms: 300,
          tokens: {},
          tool_count: 1,
          error_count: 1,
          attempt_count: 2,
        }],
        tools: [{ name: "cargo-test", status: "failed", invocations: 2, wall_ms: 300, error_count: 1 }],
        errors: [{ code: "validation_failed", stage_id: "verify", retryable: true }],
        retries: [{ attempt: 2, reason_code: "validation_failed", status: "failed", wall_ms: 300 }],
        validation: { status: "failed", checks: 4, failures: 1, source: "cargo-test" },
        coverage: { status: "complete", fields: ["stages"], missing: [] },
      }],
      consolidated: {
        task_count: 1,
        tokens_total_sum: 1_200,
        tokens_cache_read_sum: 800,        tokens_cache_write_sum: 200,
        tokens_reasoning_sum: 150,
        error_count: 1,
        retry_count: 1,
        validation: { status: "failed", checks: 4, failures: 1, source: "cargo-test" },
      },
      measured_fields: ["tokens_per_task"],
      unverified_fields: [],
      unavailable_reasons: {},
    });

    expect(report.present).toBe(true);
    if (!report.present) return;
    expect(report.tasks[0].tokens.total).toBe(1_200);
    expect(report.tasks[0].tokens.cacheRead).toBe(800);    expect(report.tasks[0].tokens.cacheWrite).toBe(200);
    expect(report.tasks[0].tokens.reasoning).toBe(150);
    expect(report.tasks[0].stages[0].status).toBe("failed");
    expect(report.tasks[0].retries[0].attempt).toBe(2);
    expect(report.tasks[0].validation.failures).toBe(1);
  });

  it("does not turn a missing token dimension into zero", () => {
    const report = parseExecutionReport({
      schema: "simplicio.execution-report/v1",
      tasks: [{ task_id: "task-1", title: "partial", tokens: { tokens_in: 5 } }],
    });
    expect(report.present).toBe(true);
    if (!report.present) return;
    expect(report.tasks[0].tokens.total).toBeNull();
  });

  it("rejects conflicting cache aliases instead of choosing a value", () => {
    expect(() => parseExecutionReport({
      schema: "simplicio.execution-report/v1",
      tasks: [{
        task_id: "task-1",
        title: "bad",
        tokens: { tokens_in: 1, tokens_out: 1, tokens_total: 2, tokens_cached: 3, cache_read_tokens: 4 },
      }],
    })).toThrow("execution_report_invalid");
  });

  it("represents an absent report explicitly", () => {
    const report = parseExecutionReport({
      schema: "simplicio.execution-report/v1",
      present: false,
      message: "not recorded",
    });
    expect(report).toMatchObject({ present: false, message: "not recorded" });
  });

  it("provides an unmistakable preview fixture with partial coverage", () => {
    const report = createPreviewExecutionReport(1_700_000_000);
    expect(report.runId).toBe("preview-run-5568");
    expect(report.coverage.status).toBe("partial");
    expect(report.tasks[1].errors[0].code).toBe("validation_failed");
  });

  it("parses bounded run history without exposing filesystem paths", () => {
    const report = parseExecutionReport({
      schema: "simplicio.execution-report/v1",
      run_id: "run-current",
      history: [{ run_id: "run-old", status: "FAIL", wall_ms: 42, task_count: 2, recorded_at_unix: 1_700_000_000 }],
    });
    expect(report.present).toBe(true);
    if (!report.present) return;
    expect(report.history).toEqual([{
      runId: "run-old",
      status: "FAIL",
      wallMs: 42,
      taskCount: 2,
      recordedAtUnix: 1_700_000_000,
    }]);
  });
});
