/** Runtime-owned cost/economy contract. The Desktop validates and presents it. */
export const COST_PROJECTION_SCHEMA = 'simplicio.desktop-cost-economy/v1';
export const MAX_COST_ROWS = 500;
export const MAX_COST_PERIODS = 7;
export const MAX_COST_EXPORT_BYTES = 64 * 1024;

export type CostWindow = 'today' | '7d' | '1m' | '3m' | '6m' | '12m' | 'custom';
export type CostExecution = 'local' | 'remote';
export type CostProvenance = 'measured' | 'provider-reported' | 'estimated' | 'mixed' | 'unavailable';
export type CostCoverageStatus = 'complete' | 'partial' | 'no_data' | 'unavailable' | 'conflicted';

export interface CostQuery {
  window?: CostWindow;
  from_epoch?: number;
  to_epoch?: number;
  provider?: string;
  model?: string;
  host?: string;
  project_id?: string;
  session_id?: string;
}

export interface CostTotals {
  event_count: number;
  actual_tokens: number | null;
  baseline_tokens: number | null;
  saved_tokens: number | null;
  actual_cost_usd: number | null;
  baseline_cost_usd: number | null;
  saved_cost_usd: number | null;
}

export interface CostBreakdownRow extends CostTotals {
  provider: string;
  model: string;
  host: string;
  project_id: string | null;
  session_id: string | null;
  execution: CostExecution;
  provenance: CostProvenance;
}

export interface CostPeriod {
  window: CostWindow;
  from_epoch: number;
  to_epoch: number;
  totals: CostTotals;
}

export interface CostPricing {
  status: 'known' | 'unknown' | 'mixed';
  version: string | null;
  sources: string[];
}

export interface CostCoverage {
  status: CostCoverageStatus;
  missing_usage_events: number;
  unpriced_events: number;
  conflicts: number;
  reason: string | null;
}

export interface CostProjectionMetadata {
  source: 'runtime';
  generated_by: 'runtime_usage_ledger';
  generated_at_epoch: number;
  report_digest: string;
  pricing: CostPricing;
  coverage: CostCoverage;
  redacted: true;
}

export interface CostProjection {
  schema: typeof COST_PROJECTION_SCHEMA;
  generated_at_epoch: number;
  query: CostQuery;
  periods: CostPeriod[];
  breakdown: CostBreakdownRow[];
  totals: CostTotals;
  metadata: CostProjectionMetadata;
}

const WINDOWS: CostWindow[] = ['today', '7d', '1m', '3m', '6m', '12m', 'custom'];
const EXECUTIONS: CostExecution[] = ['local', 'remote'];
const PROVENANCES: CostProvenance[] = [
  'measured', 'provider-reported', 'estimated', 'mixed', 'unavailable',
];
const COVERAGE: CostCoverageStatus[] = ['complete', 'partial', 'no_data', 'unavailable', 'conflicted'];
const SENSITIVE_KEY = /(^|_)(path|cwd|home|argv|prompt|secret|password|credential|authorization|api_key|access_token|refresh_token|raw_payload|raw_output|preview)(_|$)/i;

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('cost_projection_invalid');
  return value as Record<string, unknown>;
}

function rejectUnsafeKeys(value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach(rejectUnsafeKeys);
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    if (SENSITIVE_KEY.test(key)) throw new Error('cost_projection_sensitive_field');
    rejectUnsafeKeys(child);
  }
}

function text(value: unknown, max = 256): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > max
    || /[\u0000-\u001f\u007f]/.test(value) || /[\\/]/.test(value)) {
    throw new Error('cost_projection_invalid');
  }
  return value;
}

function nullableText(value: unknown): string | null {
  return value === null ? null : text(value);
}

function integer(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new Error('cost_projection_invalid');
  }
  return value;
}

function epoch(value: unknown): number {
  const result = integer(value);
  if (result > 4102444800) throw new Error('cost_projection_invalid');
  return result;
}

function nullableInteger(value: unknown): number | null {
  if (value === null) return null;
  return integer(value);
}

function money(value: unknown): number | null {
  if (value === null) return null;
  if (typeof value !== 'number' || !Number.isFinite(value) || Math.abs(value) > 1_000_000_000) {
    throw new Error('cost_projection_invalid');
  }
  return value;
}

function digest(value: unknown): string {
  if (typeof value !== 'string' || !/^sha256:[a-f0-9]{64}$/.test(value)) {
    throw new Error('cost_projection_invalid');
  }
  return value;
}

function enumValue<T extends string>(value: unknown, values: T[]): T {
  if (typeof value !== 'string' || !values.includes(value as T)) throw new Error('cost_projection_invalid');
  return value as T;
}

function validateSavings(
  actualTokens: number | null,
  baselineTokens: number | null,
  savedTokens: number | null,
  actualCost: number | null,
  baselineCost: number | null,
  savedCost: number | null,
): void {
  if ((baselineTokens === null) !== (savedTokens === null)
    || (actualCost === null || baselineCost === null) !== (savedCost === null)) {
    throw new Error('cost_projection_invalid');
  }
  if (baselineTokens !== null && savedTokens !== baselineTokens - (actualTokens ?? 0)) {
    throw new Error('cost_projection_savings_mismatch');
  }
  if (savedCost !== null && actualCost !== null && baselineCost !== null
    && Math.abs(savedCost - (baselineCost - actualCost)) > 0.00000001) {
    throw new Error('cost_projection_savings_mismatch');
  }
}

function parseTotals(value: unknown): CostTotals {
  const raw = record(value);
  const totals: CostTotals = {
    event_count: integer(raw.event_count),
    actual_tokens: nullableInteger(raw.actual_tokens),
    baseline_tokens: nullableInteger(raw.baseline_tokens),
    saved_tokens: money(raw.saved_tokens),
    actual_cost_usd: money(raw.actual_cost_usd),
    baseline_cost_usd: money(raw.baseline_cost_usd),
    saved_cost_usd: money(raw.saved_cost_usd),
  };
  validateSavings(
    totals.actual_tokens,
    totals.baseline_tokens,
    totals.saved_tokens,
    totals.actual_cost_usd,
    totals.baseline_cost_usd,
    totals.saved_cost_usd,
  );
  return totals;
}

function parseQuery(value: unknown): CostQuery {
  if (value === undefined) return {};
  const raw = record(value);
  const query: CostQuery = {};
  if (raw.window !== undefined) query.window = enumValue(raw.window, WINDOWS);
  if (raw.from_epoch !== undefined) query.from_epoch = epoch(raw.from_epoch);
  if (raw.to_epoch !== undefined) query.to_epoch = epoch(raw.to_epoch);
  if (query.from_epoch !== undefined && query.to_epoch !== undefined && query.from_epoch >= query.to_epoch) {
    throw new Error('cost_projection_invalid');
  }
  if (raw.provider !== undefined) query.provider = text(raw.provider);
  if (raw.model !== undefined) query.model = text(raw.model);
  if (raw.host !== undefined) query.host = text(raw.host);
  if (raw.project_id !== undefined) query.project_id = text(raw.project_id);
  if (raw.session_id !== undefined) query.session_id = text(raw.session_id);
  return query;
}

function parseBreakdown(value: unknown): CostBreakdownRow {
  const raw = record(value);
  const totals = parseTotals(raw);
  const execution = enumValue(raw.execution, EXECUTIONS);
  const provenance = enumValue(raw.provenance, PROVENANCES);
  return {
    ...totals,
    provider: text(raw.provider),
    model: text(raw.model),
    host: text(raw.host),
    project_id: nullableText(raw.project_id),
    session_id: nullableText(raw.session_id),
    execution,
    provenance,
  };
}

function parsePricing(value: unknown): CostPricing {
  const raw = record(value);
  const status = enumValue(raw.status, ['known', 'unknown', 'mixed'] as const);
  const version = raw.version === null ? null : text(raw.version);
  const sources = Array.isArray(raw.sources) ? raw.sources.map((item) => text(item)) : [];
  if (status === 'known' && (version === null || sources.length === 0)) throw new Error('cost_projection_pricing_invalid');
  if (status === 'unknown' && (version !== null || sources.length !== 0)) throw new Error('cost_projection_pricing_invalid');
  if (status === 'mixed' && sources.length < 2) throw new Error('cost_projection_pricing_invalid');
  return { status, version, sources };
}

function parseCoverage(value: unknown): CostCoverage {
  const raw = record(value);
  const status = enumValue(raw.status, COVERAGE);
  const coverage: CostCoverage = {
    status,
    missing_usage_events: integer(raw.missing_usage_events),
    unpriced_events: integer(raw.unpriced_events),
    conflicts: integer(raw.conflicts),
    reason: raw.reason === null ? null : text(raw.reason),
  };
  if (status === 'complete'
    && (coverage.missing_usage_events !== 0 || coverage.unpriced_events !== 0 || coverage.conflicts !== 0)) {
    throw new Error('cost_projection_coverage_invalid');
  }
  if (status === 'conflicted' && coverage.conflicts === 0) throw new Error('cost_projection_coverage_invalid');
  return coverage;
}

function sameNullableNumber(left: number | null, right: number | null): boolean {
  if (left === null || right === null) return left === right;
  return Math.abs(left - right) < 0.00000001;
}

function sumNullable(values: Array<number | null>): number | null {
  return values.some((value) => value === null) ? null : values.reduce((sum, value) => sum + (value ?? 0), 0);
}

function sumBreakdown(rows: CostBreakdownRow[]): CostTotals {
  return {
    event_count: rows.reduce((sum, row) => sum + row.event_count, 0),
    actual_tokens: sumNullable(rows.map((row) => row.actual_tokens)),
    baseline_tokens: sumNullable(rows.map((row) => row.baseline_tokens)),
    saved_tokens: sumNullable(rows.map((row) => row.saved_tokens)),
    actual_cost_usd: sumNullable(rows.map((row) => row.actual_cost_usd)),
    baseline_cost_usd: sumNullable(rows.map((row) => row.baseline_cost_usd)),
    saved_cost_usd: sumNullable(rows.map((row) => row.saved_cost_usd)),
  };
}

function sameTotals(left: CostTotals, right: CostTotals): boolean {
  return left.event_count === right.event_count
    && left.actual_tokens === right.actual_tokens
    && left.baseline_tokens === right.baseline_tokens
    && left.saved_tokens === right.saved_tokens
    && sameNullableNumber(left.actual_cost_usd, right.actual_cost_usd)
    && sameNullableNumber(left.baseline_cost_usd, right.baseline_cost_usd)
    && sameNullableNumber(left.saved_cost_usd, right.saved_cost_usd);
}

function parsePeriod(value: unknown): CostPeriod {
  const raw = record(value);
  const from = epoch(raw.from_epoch);
  const to = epoch(raw.to_epoch);
  if (from >= to) throw new Error('cost_projection_invalid');
  return {
    window: enumValue(raw.window, WINDOWS),
    from_epoch: from,
    to_epoch: to,
    totals: parseTotals(raw.totals),
  };
}

/** Parse only the Runtime's redacted cost projection; unknown fields are discarded. */
export function parseCostProjection(value: unknown): CostProjection {
  rejectUnsafeKeys(value);
  const raw = record(value);
  if (raw.schema !== COST_PROJECTION_SCHEMA) throw new Error('cost_projection_invalid');
  if (!Array.isArray(raw.periods) || raw.periods.length === 0 || raw.periods.length > MAX_COST_PERIODS) {
    throw new Error('cost_projection_invalid');
  }
  if (!Array.isArray(raw.breakdown) || raw.breakdown.length > MAX_COST_ROWS) {
    throw new Error('cost_projection_invalid');
  }
  const periods = raw.periods.map(parsePeriod);
  const windows = new Set(periods.map((period) => period.window));
  if (windows.size !== periods.length) throw new Error('cost_projection_invalid');
  const breakdown = raw.breakdown.map(parseBreakdown);
  const totals = parseTotals(raw.totals);
  const metadataRaw = record(raw.metadata);
  if (metadataRaw.source !== 'runtime' || metadataRaw.generated_by !== 'runtime_usage_ledger'
    || metadataRaw.redacted !== true) throw new Error('cost_projection_untrusted_source');
  const metadata: CostProjectionMetadata = {
    source: 'runtime',
    generated_by: 'runtime_usage_ledger',
    generated_at_epoch: epoch(metadataRaw.generated_at_epoch),
    report_digest: digest(metadataRaw.report_digest),
    pricing: parsePricing(metadataRaw.pricing),
    coverage: parseCoverage(metadataRaw.coverage),
    redacted: true,
  };
  if (!sameTotals(totals, sumBreakdown(breakdown))) {
    throw new Error('cost_projection_totals_mismatch');
  }
  if (metadata.coverage.status === 'no_data' && breakdown.length !== 0) {
    throw new Error('cost_projection_coverage_invalid');
  }
  if (metadata.coverage.status === 'unavailable' && breakdown.length !== 0) {
    throw new Error('cost_projection_coverage_invalid');
  }
  if (metadata.coverage.status === 'partial'
    && metadata.coverage.missing_usage_events === 0
    && metadata.coverage.unpriced_events === 0
    && metadata.coverage.conflicts === 0
    && breakdown.every((row) => row.provenance !== 'estimated' && row.provenance !== 'unavailable' && row.provenance !== 'mixed')) {
    throw new Error('cost_projection_coverage_invalid');
  }
  return {
    schema: COST_PROJECTION_SCHEMA,
    generated_at_epoch: epoch(raw.generated_at_epoch),
    query: parseQuery(raw.query),
    periods,
    breakdown,
    totals,
    metadata,
  };
}

function csv(value: string | number | null): string {
  const textValue = value === null ? '' : String(value);
  return '"' + textValue.replace(/"/g, '""') + '"';
}

/** Export the already validated Runtime result; the renderer performs no math. */
export function exportCostProjection(value: CostProjection, format: 'json' | 'csv'): string {
  const projection = parseCostProjection(value);
  const header = [
    'record_type', 'window', 'from_epoch', 'to_epoch', 'provider', 'model', 'host',
    'project_id', 'session_id', 'execution', 'event_count', 'actual_tokens',
    'baseline_tokens', 'saved_tokens', 'actual_cost_usd', 'baseline_cost_usd',
    'saved_cost_usd', 'provenance',
  ].join(',');
  const periodRows = projection.periods.map((period) => [
    'period', period.window, period.from_epoch, period.to_epoch, null, null, null, null, null, null,
    period.totals.event_count, period.totals.actual_tokens, period.totals.baseline_tokens,
    period.totals.saved_tokens, period.totals.actual_cost_usd, period.totals.baseline_cost_usd,
    period.totals.saved_cost_usd, null,
  ].map(csv).join(','));
  const breakdownRows = projection.breakdown.map((row) => [
    'breakdown', 'all', null, null, row.provider, row.model, row.host, row.project_id, row.session_id,
    row.execution, row.event_count, row.actual_tokens, row.baseline_tokens, row.saved_tokens,
    row.actual_cost_usd, row.baseline_cost_usd, row.saved_cost_usd, row.provenance,
  ].map(csv).join(','));
  const output = format === 'json' ? JSON.stringify(projection) : [header, ...periodRows, ...breakdownRows].join('\n');
  if (new TextEncoder().encode(output).byteLength > MAX_COST_EXPORT_BYTES) throw new Error('cost_export_too_large');
  return output;
}
