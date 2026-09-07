export const EXECUTION_REPORT_SCHEMA = "simplicio.execution-report/v1";
export const MAX_REPORT_TASKS = 512;
export const MAX_REPORT_ITEMS = 128;

export type ReportStatus = "OPEN" | "COMPLETE" | "FAIL" | "UNVERIFIED" | string;
export type ReportCoverageStatus = "complete" | "partial" | "unavailable" | "no_data";
export type ValidationStatus = "passed" | "failed" | "not_run" | "unavailable" | string;
export type ReportCostStatus = "known" | "estimated" | "unavailable" | string;

export interface ReportTokenUsage {
  input: number | null;
  output: number | null;
  cacheRead: number | null;
  cacheWrite: number | null;
  reasoning: number | null;
  total: number | null;
  inputSemantics: string;
  reasoningSemantics: string;
  costMicrousd: number | null;
  costStatus: ReportCostStatus;
  costProvenance: string;
  source: string;
}

export interface ReportStage {
  id: string;
  name: string;
  status: string;
  wallMs: number | null;
  tokens: ReportTokenUsage;
  toolCount: number;
  errorCount: number;
  attemptCount: number;
  notes: string[];
}

export interface ReportTool {
  name: string;
  status: string;
  invocations: number;
  wallMs: number | null;
  errorCount: number;
}

export interface ReportError {
  code: string;
  stageId: string | null;
  message: string | null;
  retryable: boolean | null;
}

export interface ReportRetry {
  attempt: number;
  reasonCode: string;
  status: string;
  wallMs: number | null;
}

export interface ReportValidation {
  status: ValidationStatus;
  checks: number;
  failures: number;
  source: string;
  notes: string[];
}

export interface ReportCoverage {
  status: ReportCoverageStatus;
  fields: string[];
  missing: string[];
}

export interface ReportTask {
  taskId: string;
  issue: string | null;
  title: string;
  wallMs: number | null;
  phaseLatencyMs: Record<string, unknown>;
  tokens: ReportTokenUsage;
  stages: ReportStage[];
  tools: ReportTool[];
  errors: ReportError[];
  retries: ReportRetry[];
  validation: ReportValidation;
  coverage: ReportCoverage;
  outcome: string;
  operators: string[];
  notes: string[];
}

export interface ReportConsolidated {
  taskCount: number;
  wallMsRun: number | null;
  wallMsTasksSum: number | null;
  tokensInSum: number | null;
  tokensOutSum: number | null;
  tokensTotalSum: number | null;
  tokensRollup: string;
  tokensCacheReadSum: number | null;
  tokensCacheWriteSum: number | null;
  tokensReasoningSum: number | null;
  costMicrousdSum: number | null;
  costRollup: string;
  toolInvocations: number;
  errorCount: number;
  retryCount: number;
  validation: ReportValidation;
}

export interface ReportHistoryEntry {
  runId: string;
  status: string;
  wallMs: number | null;
  taskCount: number | null;
  recordedAtUnix: number | null;
}

export interface PresentExecutionReport {
  schema: typeof EXECUTION_REPORT_SCHEMA;
  present: true;
  owner: string;
  runId: string;
  repoFingerprint: string | null;
  status: ReportStatus;
  startedAtUnix: number | null;
  finishedAtUnix: number | null;
  wallMs: number | null;
  executionProfile: string;
  operators: string[];
  tasks: ReportTask[];
  history: ReportHistoryEntry[];
  consolidated: ReportConsolidated;
  measuredFields: string[];
  unverifiedFields: string[];
  unavailableReasons: Record<string, unknown>;
  coverage: ReportCoverage;
  revision: string | null;
  fetchedAtUnix: number;
}

export interface MissingExecutionReport {
  schema: typeof EXECUTION_REPORT_SCHEMA;
  present: false;
  message: string;
  fetchedAtUnix: number;
}

export type ExecutionReport = PresentExecutionReport | MissingExecutionReport;

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("execution_report_invalid");
  return value as Record<string, unknown>;
}

function optionalRecord(value: unknown): Record<string, unknown> {
  if (value === undefined || value === null) return {};
  return record(value);
}

function text(value: unknown, fallback: string, max = 512): string {
  if (value === undefined || value === null) return fallback;
  if (typeof value !== "string" || value.length === 0 || value.length > max || /[\u0000-\u001f\u007f]/.test(value)) {
    throw new Error("execution_report_invalid");
  }
  return value;
}

function optionalText(value: unknown, max = 512): string | null {
  if (value === undefined || value === null) return null;
  return text(value, "", max);
}

function nonNegative(value: unknown): number | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) throw new Error("execution_report_invalid");
  return value;
}

function booleanOrNull(value: unknown): boolean | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== "boolean") throw new Error("execution_report_invalid");
  return value;
}

function array(value: Record<string, unknown>, key: string, max = MAX_REPORT_ITEMS): unknown[] {
  const candidate = value[key];
  if (candidate === undefined || candidate === null) return [];
  if (!Array.isArray(candidate) || candidate.length > max) throw new Error("execution_report_invalid");
  return candidate;
}

function strings(value: Record<string, unknown>, key: string, max = MAX_REPORT_ITEMS): string[] {
  return array(value, key, max).map((item) => text(item, ""));
}

function metric(value: Record<string, unknown>, primary: string, secondary?: string): number | null {
  const first = nonNegative(value[primary]);
  const second = secondary ? nonNegative(value[secondary]) : null;
  if (first !== null && second !== null && first !== second) throw new Error("execution_report_invalid");
  return first ?? second;
}

const knownCoverage = new Set<ReportCoverageStatus>(["complete", "partial", "unavailable", "no_data"]);

function parseCoverage(raw: unknown, fallbackMissing: string[] = []): ReportCoverage {
  const value = optionalRecord(raw);
  const status = text(value.status, fallbackMissing.length ? "partial" : "unavailable") as ReportCoverageStatus;
  if (!knownCoverage.has(status)) throw new Error("execution_report_invalid");
  const missing = strings(value, "missing");
  return {
    status,
    fields: strings(value, "fields"),
    missing: missing.length ? missing : fallbackMissing,
  };
}

function parseTokens(raw: unknown): ReportTokenUsage {
  const value = optionalRecord(raw);
  const input = nonNegative(value.tokens_in);
  const output = nonNegative(value.tokens_out);
  const total = nonNegative(value.tokens_total);
  let expectedTotal: number | null = null;
  if (input !== null && output !== null) {
    if (input > Number.MAX_SAFE_INTEGER - output) throw new Error("execution_report_invalid");
    expectedTotal = input + output;
  }
  if (total !== null && expectedTotal !== null && total !== expectedTotal) throw new Error("execution_report_invalid");
  if (total !== null && expectedTotal === null) throw new Error("execution_report_invalid");
  return {
    input,
    output,
    cacheRead: metric(value, "tokens_cached", "cache_read_tokens"),
    cacheWrite: metric(value, "cache_write_tokens", "tokens_cache_write"),
    reasoning: nonNegative(value.tokens_reasoning),
    total: expectedTotal,
    inputSemantics: text(value.input_semantics, "unknown", 96),
    reasoningSemantics: text(value.reasoning_semantics, "unknown", 96),
    costMicrousd: nonNegative(value.cost_microusd),
    costStatus: text(value.cost_status, "unavailable", 48),
    costProvenance: text(value.cost_provenance, "unavailable", 96),
    source: text(value.source, "absent", 96),
  };
}

function parseStage(raw: unknown): ReportStage {
  const value = record(raw);
  return {
    id: text(value.stage_id ?? value.id, "unknown", 128),
    name: text(value.name, "Etapa não identificada"),
    status: text(value.status, "unavailable", 96),
    wallMs: nonNegative(value.wall_ms),
    tokens: parseTokens(value.tokens),
    toolCount: nonNegative(value.tool_count) ?? 0,
    errorCount: nonNegative(value.error_count) ?? 0,
    attemptCount: nonNegative(value.attempt_count) ?? 0,
    notes: strings(value, "notes"),
  };
}

function parseTool(raw: unknown): ReportTool {
  const value = record(raw);
  return {
    name: text(value.name, "tool", 128),
    status: text(value.status, "unavailable", 96),
    invocations: nonNegative(value.invocations) ?? 0,
    wallMs: nonNegative(value.wall_ms),
    errorCount: nonNegative(value.error_count) ?? 0,
  };
}

function parseError(raw: unknown): ReportError {
  const value = record(raw);
  return {
    code: text(value.code, "unknown_error", 128),
    stageId: optionalText(value.stage_id, 128),
    message: optionalText(value.message, 256),
    retryable: booleanOrNull(value.retryable),
  };
}

function parseRetry(raw: unknown): ReportRetry {
  const value = record(raw);
  return {
    attempt: nonNegative(value.attempt) ?? 0,
    reasonCode: text(value.reason_code, "unknown_retry", 128),
    status: text(value.status, "unavailable", 96),
    wallMs: nonNegative(value.wall_ms),
  };
}

function parseValidation(raw: unknown): ReportValidation {
  const value = optionalRecord(raw);
  return {
    status: text(value.status, "unavailable", 48),
    checks: nonNegative(value.checks) ?? 0,
    failures: nonNegative(value.failures) ?? 0,
    source: text(value.source, "not_recorded", 128),
    notes: strings(value, "notes"),
  };
}

function parseTask(raw: unknown): ReportTask {
  const value = record(raw);
  const phaseLatency = optionalRecord(value.phase_latency_ms);
  return {
    taskId: text(value.task_id, "unknown", 256),
    issue: optionalText(value.issue, 128),
    title: text(value.title, "Tarefa sem título"),
    wallMs: nonNegative(value.wall_ms),
    phaseLatencyMs: phaseLatency,
    tokens: parseTokens(value.tokens),
    stages: array(value, "stages").map(parseStage),
    tools: array(value, "tools").map(parseTool),
    errors: array(value, "errors").map(parseError),
    retries: array(value, "retries").map(parseRetry),
    validation: parseValidation(value.validation),
    coverage: parseCoverage(value.coverage),
    outcome: text(value.outcome, "UNVERIFIED", 64),
    operators: strings(value, "operators_used"),
    notes: strings(value, "notes"),
  };
}

function parseConsolidated(raw: unknown, taskCount: number): ReportConsolidated {
  const value = optionalRecord(raw);
  const tokensRollup = text(value.tokens_rollup, "complete", 32);
  return {
    taskCount: nonNegative(value.task_count) ?? taskCount,
    wallMsRun: nonNegative(value.wall_ms_run),
    wallMsTasksSum: nonNegative(value.wall_ms_tasks_sum),
    tokensInSum: nonNegative(value.tokens_in_sum),
    tokensOutSum: nonNegative(value.tokens_out_sum),
    tokensTotalSum: tokensRollup === "partial" ? null : nonNegative(value.tokens_total_sum),
    tokensRollup,
    tokensCacheReadSum: nonNegative(value.tokens_cache_read_sum),
    tokensCacheWriteSum: nonNegative(value.tokens_cache_write_sum),
    tokensReasoningSum: nonNegative(value.tokens_reasoning_sum),
    costMicrousdSum: nonNegative(value.cost_microusd_sum),
    costRollup: text(value.cost_rollup, "unavailable", 32),
    toolInvocations: nonNegative(value.tool_invocations) ?? 0,
    errorCount: nonNegative(value.error_count) ?? 0,
    retryCount: nonNegative(value.retry_count) ?? 0,
    validation: parseValidation(value.validation),
  };
}

function parseHistory(raw: unknown): ReportHistoryEntry[] {
  if (raw === undefined || raw === null) return [];
  if (!Array.isArray(raw) || raw.length > MAX_REPORT_ITEMS) throw new Error("execution_report_invalid");
  return raw.map((item) => {
    const value = record(item);
    return {
      runId: text(value.run_id, "unknown", 128),
      status: text(value.status, "UNVERIFIED", 64),
      wallMs: nonNegative(value.wall_ms),
      taskCount: nonNegative(value.task_count),
      recordedAtUnix: nonNegative(value.recorded_at_unix),
    };
  });
}

export function parseExecutionReport(raw: unknown, fetchedAtUnix = Math.floor(Date.now() / 1000)): ExecutionReport {
  const value = record(raw);
  if (value.schema !== EXECUTION_REPORT_SCHEMA) throw new Error("execution_report_invalid");
  if (value.present === false) {
    return {
      schema: EXECUTION_REPORT_SCHEMA,
      present: false,
      message: text(value.message, "Nenhum relatório de execução foi registrado."),
      fetchedAtUnix,
    };
  }
  const tasks = array(value, "tasks", MAX_REPORT_TASKS).map(parseTask);
  const unverifiedFields = strings(value, "unverified_fields");
  const measuredFields = strings(value, "measured_fields");
  const coverage = parseCoverage(value.coverage, unverifiedFields);
  return {
    schema: EXECUTION_REPORT_SCHEMA,
    present: true,
    owner: text(value.owner, "simplicio-runtime", 128),
    runId: text(value.run_id, "unknown", 256),
    repoFingerprint: optionalText(value.repo_fingerprint, 128),
    status: text(value.status, "UNVERIFIED", 64),
    startedAtUnix: nonNegative(value.started_at_unix),
    finishedAtUnix: nonNegative(value.finished_at_unix),
    wallMs: nonNegative(value.wall_ms),
    executionProfile: text(value.execution_profile, "runtime-backed", 128),
    operators: strings(value, "operators_used"),
    tasks,
    history: parseHistory(value.history),
    consolidated: parseConsolidated(value.consolidated, tasks.length),
    measuredFields,
    unverifiedFields,
    unavailableReasons: optionalRecord(value.unavailable_reasons),
    coverage,
    revision: optionalText(value.revision, 128),
    fetchedAtUnix,
  };
}

function demoTokens(input: number, output: number, cacheRead: number | null, reasoning: number | null, source: string): ReportTokenUsage {
  return {
    input,
    output,
    cacheRead,
    cacheWrite: null,
    reasoning,
    total: input + output,
    inputSemantics: "uncached_only",
    reasoningSemantics: reasoning === null ? "unknown" : "included_in_output",
    costMicrousd: null,
    costStatus: "unavailable",
    costProvenance: "unavailable",
    source,
  };
}

export function createPreviewExecutionReport(fetchedAtUnix = Math.floor(Date.now() / 1000)): PresentExecutionReport {
  const mapperTokens = demoTokens(420, 180, 320, null, "measured");
  const repairTokens = demoTokens(1_000, 200, 800, 150, "provider-reported");
  const task = (taskId: string, title: string, outcome: string, tokens: ReportTokenUsage, stage: ReportStage, tools: ReportTool[], errors: ReportError[], retries: ReportRetry[], validation: ReportValidation, issue: string | null): ReportTask => ({
    taskId,
    issue,
    title,
    wallMs: stage.wallMs,
    phaseLatencyMs: {},
    tokens,
    stages: [stage],
    tools,
    errors,
    retries,
    validation,
    coverage: {
      status: errors.length || retries.length ? "partial" : "complete",
      fields: ["stages", "tools", "validation"],
      missing: errors.length || retries.length ? [] : ["errors", "retries"],
    },
    outcome,
    operators: ["simplicio-loop", "simplicio-dev-cli"],
    notes: [],
  });
  const mapperValidation: ReportValidation = { status: "passed", checks: 3, failures: 0, source: "runtime", notes: [] };
  const failedValidation: ReportValidation = { status: "failed", checks: 5, failures: 1, source: "cargo-test", notes: ["Uma verificação falhou; detalhes preservados como evidência."] };
  return {
    schema: EXECUTION_REPORT_SCHEMA,
    present: true,
    owner: "simplicio-runtime",
    runId: "preview-run-5568",
    repoFingerprint: null,
    status: "FAIL",
    startedAtUnix: fetchedAtUnix - 68,
    finishedAtUnix: fetchedAtUnix,
    wallMs: 68_000,
    executionProfile: "runtime-backed",
    operators: ["simplicio-loop", "simplicio-mapper", "simplicio-dev-cli"],
    tasks: [
      task("map", "Mapear contexto do épico", "COMPLETE", mapperTokens, {
        id: "discover",
        name: "Descoberta",
        status: "complete",
        wallMs: 820,
        tokens: mapperTokens,
        toolCount: 2,
        errorCount: 0,
        attemptCount: 1,
        notes: [],
      }, [{ name: "simplicio_map", status: "complete", invocations: 1, wallMs: 640, errorCount: 0 }], [], [], mapperValidation, "#5568"),
      task("implement", "Integrar telemetria por tarefa", "FAIL", repairTokens, {
        id: "verify",
        name: "Validação",
        status: "failed",
        wallMs: 3_400,
        tokens: repairTokens,
        toolCount: 1,
        errorCount: 1,
        attemptCount: 2,
        notes: [],
      }, [{ name: "cargo test", status: "failed", invocations: 2, wallMs: 3_400, errorCount: 1 }], [{ code: "validation_failed", stageId: "verify", message: "A validação não foi confirmada.", retryable: true }], [{ attempt: 2, reasonCode: "validation_failed", status: "failed", wallMs: 3_400 }], failedValidation, "#5569"),
    ],
    history: [{
      runId: "preview-run-5568",
      status: "FAIL",
      wallMs: 68_000,
      taskCount: 2,
      recordedAtUnix: fetchedAtUnix,
    }],
    consolidated: {
      taskCount: 2,
      wallMsRun: 68_000,
      wallMsTasksSum: 4_220,
      tokensInSum: 1_420,
      tokensOutSum: 380,
      tokensTotalSum: 1_800,
      tokensCacheReadSum: 1_120,      tokensRollup: "complete",
      tokensCacheWriteSum: null,
      tokensReasoningSum: 150,
      costMicrousdSum: null,
      costRollup: "unavailable",
      toolInvocations: 3,
      errorCount: 1,
      retryCount: 1,
      validation: { status: "failed", checks: 8, failures: 1, source: "runtime", notes: [] },
    },
    measuredFields: ["run_id", "started_at_unix", "task_wall_ms", "tokens_per_task"],
    unverifiedFields: ["cpu_percent", "cost_microusd"],
    unavailableReasons: { cost_microusd: "no pricing receipt in preview" },
    coverage: { status: "partial", fields: ["tasks", "stages", "tools", "validation"], missing: ["cost_microusd", "otel"] },
    revision: "preview:2",
    fetchedAtUnix,
  };
}

export function downloadExecutionReport(report: ExecutionReport): void {
  if (typeof document === "undefined") return;
  const payload = JSON.stringify(report, null, 2);
  const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "simplicio-execution-report.json";
  link.click();
  URL.revokeObjectURL(url);
}
