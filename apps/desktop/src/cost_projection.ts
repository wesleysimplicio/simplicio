/** Runtime-owned Desktop cost projection. The renderer validates and presents; it never derives cost. */
export const COST_PROJECTION_SCHEMA = 'simplicio.desktop-cost-projection/v1';
export const MAX_COST_ROWS = 500;
export const MAX_COST_IDENTITY_ITEMS = 500;
export const MAX_COST_EXPORT_BYTES = 64 * 1024;

export type CostExecution = 'local' | 'remote';
export type CostProvenance = 'measured' | 'provider-reported' | 'estimated' | 'unavailable';
export type CostCoverageStatus = 'complete' | 'partial' | 'no_data' | 'unavailable' | 'conflicted';
export type CostConfidence = 'high' | 'medium' | 'blocked';

export interface CostQuery {
  from_epoch?: number;
  to_epoch?: number;
  provider?: string;
  model?: string;
  host?: string;
  project_id?: string;
  session_id?: string;
}

export interface CostPricing {
  status: 'known' | 'mixed' | 'unavailable';
  identity: string | null;
  version: string | null;
  versions: string[];
  sources: string[];
}

export interface CostBaseline {
  identity_status: 'known' | 'mixed' | 'unknown';
  versions: string[];
  methods: string[];
  values_status: 'known' | 'mixed' | 'unavailable';
  reason: string | null;
}

export interface CostConfidenceSummary {
  actual: CostConfidence;
  baseline: CostConfidence;
  savings: CostConfidence;
}

export interface CostTotals {
  event_count: number;
  actual_tokens: number | null;
  actual_cost_usd: number | null;
  baseline_tokens: number | null;
  baseline_cost_usd: number | null;
  saved_tokens: number | null;
  saved_cost_usd: number | null;
}

export interface CostRow extends CostTotals {
  provider: string;
  model: string;
  host: string;
  project_id: string;
  session_id: string;
  execution: CostExecution;
  state: CostProvenance;
  confidence: CostConfidence;
  reason: string | null;
}

export interface CostCoverage {
  status: CostCoverageStatus;
  missing_usage_events: number;
  unpriced_events: number;
  providers: string[];
  reason: string | null;
}

export interface CostProjectionMetadata {
  source: 'runtime';
  generated_by: 'runtime_usage_ledger';
  revision: string;
  report_digest: string;
  coverage: CostCoverage;
  redacted: true;
}

export interface CostProjection {
  schema: typeof COST_PROJECTION_SCHEMA;
  generated_at_epoch: number;
  query: CostQuery;
  usage_revision: string;
  pricing: CostPricing;
  baseline: CostBaseline;
  confidence: CostConfidenceSummary;
  rows: CostRow[];
  totals: CostTotals;
  metadata: CostProjectionMetadata;
}

const EXECUTIONS: CostExecution[] = ['local', 'remote'];
const PROVENANCES: CostProvenance[] = ['measured', 'provider-reported', 'estimated', 'unavailable'];
const CONFIDENCES: CostConfidence[] = ['high', 'medium', 'blocked'];
const COVERAGE: CostCoverageStatus[] = ['complete', 'partial', 'no_data', 'unavailable', 'conflicted'];
const SENSITIVE_KEY = /(^|_)(path|cwd|home|argv|prompt|secret|password|credential|authorization|api_key|access_token|refresh_token|raw_payload|raw_output|preview)(_|$)/i;

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('cost_projection_invalid');
  return value as Record<string, unknown>;
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

function digest(value: unknown): string {
  if (typeof value !== 'string' || !/^sha256:[a-f0-9]{64}$/.test(value)) throw new Error('cost_projection_invalid');
  return value;
}

function integer(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new Error('cost_projection_invalid');
  return value;
}

function epoch(value: unknown): number {
  const result = integer(value);
  if (result > 4_102_444_800) throw new Error('cost_projection_invalid');
  return result;
}

function nullableInteger(value: unknown): number | null {
  return value === null ? null : integer(value);
}

function money(value: unknown): number | null {
  if (value === null) return null;
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1_000_000_000) {
    throw new Error('cost_projection_invalid');
  }
  return value;
}

function enumValue<T extends string>(value: unknown, values: T[]): T {
  if (typeof value !== 'string' || !values.includes(value as T)) throw new Error('cost_projection_invalid');
  return value as T;
}

function identityArray(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > MAX_COST_IDENTITY_ITEMS) throw new Error('cost_projection_invalid');
  const values = value.map(item => text(item));
  if (new Set(values).size !== values.length) throw new Error('cost_projection_invalid');
  return values;
}

function rejectSensitiveKeys(value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach(rejectSensitiveKeys);
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    if (SENSITIVE_KEY.test(key)) throw new Error('cost_projection_sensitive_field');
    rejectSensitiveKeys(child);
  }
}

function parseQuery(value: unknown): CostQuery {
  if (value === undefined) return {};
  const raw = object(value);
  const query: CostQuery = {};
  if (raw.from_epoch !== undefined) query.from_epoch = epoch(raw.from_epoch);
  if (raw.to_epoch !== undefined) query.to_epoch = epoch(raw.to_epoch);
  if (query.from_epoch !== undefined && query.to_epoch !== undefined && query.from_epoch >= query.to_epoch) {
    throw new Error('cost_projection_invalid');
  }
  for (const key of ['provider', 'model', 'host', 'project_id', 'session_id'] as const) {
    if (raw[key] !== undefined) query[key] = text(raw[key]);
  }
  return query;
}

function validateSavings(totals: CostTotals): void {
  const tokensKnown = totals.actual_tokens !== null && totals.baseline_tokens !== null;
  if ((totals.saved_tokens !== null) !== tokensKnown) throw new Error('cost_projection_savings_mismatch');
  if (tokensKnown && totals.saved_tokens !== totals.baseline_tokens! - totals.actual_tokens!) {
    throw new Error('cost_projection_savings_mismatch');
  }
  const costsKnown = totals.actual_cost_usd !== null && totals.baseline_cost_usd !== null;
  if ((totals.saved_cost_usd !== null) !== costsKnown) throw new Error('cost_projection_savings_mismatch');
  if (costsKnown && Math.abs(totals.saved_cost_usd! - (totals.baseline_cost_usd! - totals.actual_cost_usd!)) > 0.00000001) {
    throw new Error('cost_projection_savings_mismatch');
  }
}

function parseTotals(value: unknown): CostTotals {
  const raw = object(value);
  const totals: CostTotals = {
    event_count: integer(raw.event_count),
    actual_tokens: nullableInteger(raw.actual_tokens),
    actual_cost_usd: money(raw.actual_cost_usd),
    baseline_tokens: nullableInteger(raw.baseline_tokens),
    baseline_cost_usd: money(raw.baseline_cost_usd),
    saved_tokens: nullableInteger(raw.saved_tokens),
    saved_cost_usd: money(raw.saved_cost_usd),
  };
  validateSavings(totals);
  return totals;
}

function parseRow(value: unknown): CostRow {
  const raw = object(value);
  const row: CostRow = {
    provider: text(raw.provider),
    model: text(raw.model),
    host: text(raw.host),
    project_id: digest(raw.project_id),
    session_id: digest(raw.session_id),
    execution: enumValue(raw.execution, EXECUTIONS),
    event_count: integer(raw.event_count),
    actual_tokens: nullableInteger(raw.actual_tokens),
    actual_cost_usd: money(raw.actual_cost_usd),
    baseline_tokens: nullableInteger(raw.baseline_tokens),
    baseline_cost_usd: money(raw.baseline_cost_usd),
    saved_tokens: nullableInteger(raw.saved_tokens),
    saved_cost_usd: money(raw.saved_cost_usd),
    state: enumValue(raw.state, PROVENANCES),
    confidence: enumValue(raw.confidence, CONFIDENCES),
    reason: nullableText(raw.reason),
  };
  validateSavings(row);
  return row;
}

function parseCoverage(value: unknown): CostCoverage {
  const raw = object(value);
  const coverage: CostCoverage = {
    status: enumValue(raw.status, COVERAGE),
    missing_usage_events: integer(raw.missing_usage_events),
    unpriced_events: integer(raw.unpriced_events),
    providers: identityArray(raw.providers ?? []),
    reason: nullableText(raw.reason),
  };
  if (coverage.status === 'complete'
    && (coverage.missing_usage_events !== 0 || coverage.unpriced_events !== 0)) throw new Error('cost_projection_coverage_mismatch');
  return coverage;
}

function sumNullable(values: Array<number | null>): number | null {
  if (values.some(value => value === null)) return null;
  return values.reduce<number>((sum, value) => sum + (value ?? 0), 0);
}

function sumRows(rows: CostRow[]): CostTotals {
  const totals: CostTotals = {
    event_count: rows.reduce((sum, row) => sum + row.event_count, 0),
    actual_tokens: sumNullable(rows.map(row => row.actual_tokens)),
    actual_cost_usd: sumNullable(rows.map(row => row.actual_cost_usd)),
    baseline_tokens: sumNullable(rows.map(row => row.baseline_tokens)),
    baseline_cost_usd: sumNullable(rows.map(row => row.baseline_cost_usd)),
    saved_tokens: sumNullable(rows.map(row => row.saved_tokens)),
    saved_cost_usd: sumNullable(rows.map(row => row.saved_cost_usd)),
  };
  validateSavings(totals);
  return totals;
}

function sameNullable(left: number | null, right: number | null): boolean {
  return left === null || right === null ? left === right : Math.abs(left - right) <= 0.00000001;
}

function sameTotals(left: CostTotals, right: CostTotals): boolean {
  return left.event_count === right.event_count
    && left.actual_tokens === right.actual_tokens
    && sameNullable(left.actual_cost_usd, right.actual_cost_usd)
    && left.baseline_tokens === right.baseline_tokens
    && sameNullable(left.baseline_cost_usd, right.baseline_cost_usd)
    && left.saved_tokens === right.saved_tokens
    && sameNullable(left.saved_cost_usd, right.saved_cost_usd);
}

function parsePricing(value: unknown): CostPricing {
  const raw = object(value);
  const pricing: CostPricing = {
    status: enumValue(raw.status, ['known', 'mixed', 'unavailable'] as const),
    identity: raw.identity === null ? null : digest(raw.identity),
    version: raw.version === null ? null : text(raw.version),
    versions: identityArray(raw.versions ?? []),
    sources: identityArray(raw.sources ?? []),
  };
  if (pricing.status === 'unavailable' && (pricing.identity !== null || pricing.version !== null
    || pricing.versions.length !== 0 || pricing.sources.length !== 0)) throw new Error('cost_projection_pricing_invalid');
  if (pricing.status === 'known' && (pricing.identity === null || pricing.version === null
    || pricing.versions.length === 0 || pricing.sources.length === 0)) throw new Error('cost_projection_pricing_invalid');
  if (pricing.status === 'mixed' && (pricing.identity === null || pricing.sources.length === 0)) throw new Error('cost_projection_pricing_invalid');
  return pricing;
}

function parseBaseline(value: unknown): CostBaseline {
  const raw = object(value);
  const baseline: CostBaseline = {
    identity_status: enumValue(raw.identity_status, ['known', 'mixed', 'unknown'] as const),
    versions: identityArray(raw.versions ?? []),
    methods: identityArray(raw.methods ?? []),
    values_status: enumValue(raw.values_status, ['known', 'mixed', 'unavailable'] as const),
    reason: nullableText(raw.reason),
  };
  if (baseline.identity_status === 'known' && (baseline.versions.length !== 1 || baseline.methods.length !== 1)) {
    throw new Error('cost_projection_baseline_invalid');
  }
  if (baseline.identity_status === 'unknown' && (baseline.versions.length !== 0 || baseline.methods.length !== 0)) {
    throw new Error('cost_projection_baseline_invalid');
  }
  return baseline;
}

/** Parse only the Runtime's redacted cost projection; unknown fields are intentionally discarded. */
export function parseCostProjection(value: unknown): CostProjection {
  rejectSensitiveKeys(value);
  const raw = object(value);
  if (raw.schema !== COST_PROJECTION_SCHEMA) throw new Error('cost_projection_invalid');
  const rowsRaw = raw.rows;
  if (!Array.isArray(rowsRaw) || rowsRaw.length > MAX_COST_ROWS) throw new Error('cost_projection_invalid');
  const rows = rowsRaw.map(parseRow);
  const totals = parseTotals(raw.totals);
  if (!sameTotals(totals, sumRows(rows))) throw new Error('cost_projection_totals_mismatch');
  const metadataRaw = object(raw.metadata);
  if (metadataRaw.source !== 'runtime' || metadataRaw.generated_by !== 'runtime_usage_ledger' || metadataRaw.redacted !== true) {
    throw new Error('cost_projection_untrusted_source');
  }
  const metadata: CostProjectionMetadata = {
    source: 'runtime',
    generated_by: 'runtime_usage_ledger',
    revision: digest(metadataRaw.revision),
    report_digest: digest(metadataRaw.report_digest),
    coverage: parseCoverage(metadataRaw.coverage),
    redacted: true,
  };
  if (metadata.coverage.status === 'no_data' || metadata.coverage.status === 'unavailable') {
    if (rows.length !== 0 || totals.event_count !== 0) throw new Error('cost_projection_coverage_mismatch');
  }
  if (metadata.coverage.status === 'partial' && metadata.coverage.missing_usage_events === 0
    && metadata.coverage.unpriced_events === 0 && rows.every(row => row.confidence !== 'blocked')) {
    throw new Error('cost_projection_coverage_mismatch');
  }
  const confidence = object(raw.confidence);
  return {
    schema: COST_PROJECTION_SCHEMA,
    generated_at_epoch: epoch(raw.generated_at_epoch),
    query: parseQuery(raw.query),
    usage_revision: digest(raw.usage_revision),
    pricing: parsePricing(raw.pricing),
    baseline: parseBaseline(raw.baseline),
    confidence: {
      actual: enumValue(confidence.actual, CONFIDENCES),
      baseline: enumValue(confidence.baseline, CONFIDENCES),
      savings: enumValue(confidence.savings, CONFIDENCES),
    },
    rows,
    totals,
    metadata,
  };
}

function csv(value: string | number | null): string {
  const textValue = value === null ? '' : String(value);
  return `"${textValue.replace(/"/g, '""')}"`;
}

/** Export the validated Runtime result without renderer-side arithmetic. */
export function exportCostProjection(value: CostProjection, format: 'json' | 'csv'): string {
  const projection = parseCostProjection(value);
  const output = format === 'json' ? JSON.stringify(projection) : [
    ['record_type', 'provider', 'model', 'host', 'project_id', 'session_id', 'execution', 'event_count',
      'actual_tokens', 'actual_cost_usd', 'baseline_tokens', 'baseline_cost_usd', 'saved_tokens',
      'saved_cost_usd', 'state', 'confidence', 'reason'].join(','),
    ...projection.rows.map(row => [
      'row', row.provider, row.model, row.host, row.project_id, row.session_id, row.execution, row.event_count,
      row.actual_tokens, row.actual_cost_usd, row.baseline_tokens, row.baseline_cost_usd, row.saved_tokens,
      row.saved_cost_usd, row.state, row.confidence, row.reason,
    ].map(csv).join(',')),
  ].join('\n');
  if (new TextEncoder().encode(output).byteLength > MAX_COST_EXPORT_BYTES) throw new Error('cost_export_too_large');
  return output;
}
