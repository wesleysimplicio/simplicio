/** Runtime-owned Desktop cost projection. The renderer validates and presents; it never derives cost. */
export const COST_PROJECTION_SCHEMA = 'simplicio.desktop-cost-projection/v1';
export const MAX_COST_ROWS = 500;
export const MAX_COST_IDENTITY_ITEMS = 500;
export const MAX_COST_EXPORT_BYTES = 64 * 1024;

export type CostExecution = 'local' | 'remote';
export type CostProvenance = 'measured' | 'provider-reported' | 'estimated' | 'unavailable';
export type CostCoverageStatus = 'complete' | 'partial' | 'no_data';
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
  identity_status: 'known' | 'mixed' | 'unknown' | 'unavailable';
  versions: string[];
  methods: string[];
  values_status: 'unavailable';
  reason: 'baseline_values_not_recorded';
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
const COVERAGE: CostCoverageStatus[] = ['complete', 'partial', 'no_data'];
const SENSITIVE_KEY = /(^|_)(path|cwd|home|argv|prompt|secret|password|credential|authorization|api_key|access_token|refresh_token|raw_payload|raw_output|preview)(_|$)/i;

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('cost_projection_invalid');
  return value as Record<string, unknown>;
}

function exactObject(
  value: unknown,
  allowed: readonly string[],
  required: readonly string[] = allowed,
): Record<string, unknown> {
  const raw = object(value);
  if (Object.keys(raw).some(key => !allowed.includes(key))
    || required.some(key => !(key in raw))) {
    throw new Error('cost_projection_invalid');
  }
  return raw;
}

function text(value: unknown, max = 256): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > max
    || !/^[\x20-\x7e]+$/.test(value)) {
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

function positiveInteger(value: unknown): number {
  const result = integer(value);
  if (result < 1) throw new Error('cost_projection_invalid');
  return result;
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
  const raw = exactObject(value, [
    'from_epoch', 'to_epoch', 'provider', 'model', 'host', 'project_id', 'session_id',
  ], []);
  const query: CostQuery = {};
  if (raw.from_epoch !== undefined) query.from_epoch = epoch(raw.from_epoch);
  if (raw.to_epoch !== undefined) query.to_epoch = epoch(raw.to_epoch);
  if (query.from_epoch !== undefined && query.to_epoch !== undefined && query.from_epoch >= query.to_epoch) {
    throw new Error('cost_projection_invalid');
  }
  for (const key of ['provider', 'model', 'host'] as const) {
    if (raw[key] !== undefined) query[key] = text(raw[key]);
  }
  for (const key of ['project_id', 'session_id'] as const) {
    if (raw[key] !== undefined) query[key] = digest(raw[key]);
  }
  return query;
}

function parseTotals(value: unknown): CostTotals {
  const raw = exactObject(value, [
    'event_count', 'actual_tokens', 'actual_cost_usd', 'baseline_tokens',
    'baseline_cost_usd', 'saved_tokens', 'saved_cost_usd',
  ]);
  const totals: CostTotals = {
    event_count: integer(raw.event_count),
    actual_tokens: nullableInteger(raw.actual_tokens),
    actual_cost_usd: money(raw.actual_cost_usd),
    baseline_tokens: nullableInteger(raw.baseline_tokens),
    baseline_cost_usd: money(raw.baseline_cost_usd),
    saved_tokens: nullableInteger(raw.saved_tokens),
    saved_cost_usd: money(raw.saved_cost_usd),
  };
  if (totals.baseline_tokens !== null || totals.baseline_cost_usd !== null
    || totals.saved_tokens !== null || totals.saved_cost_usd !== null) {
    throw new Error('cost_projection_invalid');
  }
  return totals;
}

function parseRow(value: unknown): CostRow {
  const raw = exactObject(value, [
    'provider', 'model', 'host', 'project_id', 'session_id', 'execution', 'event_count',
    'actual_tokens', 'actual_cost_usd', 'baseline_tokens', 'baseline_cost_usd',
    'saved_tokens', 'saved_cost_usd', 'state', 'confidence', 'reason',
  ]);
  const row: CostRow = {
    provider: text(raw.provider),
    model: text(raw.model),
    host: text(raw.host),
    project_id: digest(raw.project_id),
    session_id: digest(raw.session_id),
    execution: enumValue(raw.execution, EXECUTIONS),
    event_count: positiveInteger(raw.event_count),
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
  if (row.baseline_tokens !== null || row.baseline_cost_usd !== null
    || row.saved_tokens !== null || row.saved_cost_usd !== null) {
    throw new Error('cost_projection_invalid');
  }
  return row;
}

function parseCoverage(value: unknown): CostCoverage {
  const raw = exactObject(value, [
    'status', 'missing_usage_events', 'unpriced_events', 'providers', 'reason',
  ]);
  const coverage: CostCoverage = {
    status: enumValue(raw.status, ['complete', 'partial', 'no_data'] as const),
    missing_usage_events: integer(raw.missing_usage_events),
    unpriced_events: integer(raw.unpriced_events),
    providers: identityArray(raw.providers),
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
  const raw = exactObject(value, ['status', 'identity', 'version', 'versions', 'sources']);
  const pricing: CostPricing = {
    status: enumValue(raw.status, ['known', 'mixed', 'unavailable'] as const),
    identity: raw.identity === null ? null : digest(raw.identity),
    version: raw.version === null ? null : text(raw.version),
    versions: identityArray(raw.versions),
    sources: identityArray(raw.sources),
  };
  if (pricing.sources.some(source => !['measured', 'provider-reported', 'estimated'].includes(source))) {
    throw new Error('cost_projection_invalid');
  }
  if (pricing.status === 'unavailable' && (pricing.identity !== null || pricing.version !== null
    || pricing.sources.length !== 0)) throw new Error('cost_projection_pricing_invalid');
  if (['known', 'mixed'].includes(pricing.status)
    && (pricing.identity === null || pricing.versions.length === 0 || pricing.sources.length === 0)) {
    throw new Error('cost_projection_pricing_invalid');
  }
  return pricing;
}

function parseBaseline(value: unknown): CostBaseline {
  const raw = exactObject(value, [
    'identity_status', 'versions', 'methods', 'values_status', 'reason',
  ]);
  const baseline: CostBaseline = {
    identity_status: enumValue(raw.identity_status, ['known', 'mixed', 'unknown', 'unavailable'] as const),
    versions: identityArray(raw.versions),
    methods: identityArray(raw.methods),
    values_status: 'unavailable',
    reason: 'baseline_values_not_recorded',
  };
  if (raw.values_status !== 'unavailable' || raw.reason !== 'baseline_values_not_recorded') {
    throw new Error('cost_projection_baseline_invalid');
  }
  return baseline;
}

/** Parse only the Runtime's redacted cost projection; unknown fields are intentionally discarded. */
export function parseCostProjection(value: unknown): CostProjection {
  rejectSensitiveKeys(value);
  const raw = exactObject(value, [
    'schema', 'generated_at_epoch', 'query', 'usage_revision', 'pricing', 'baseline',
    'confidence', 'rows', 'totals', 'metadata',
  ]);
  if (raw.schema !== COST_PROJECTION_SCHEMA) throw new Error('cost_projection_invalid');
  const rowsRaw = raw.rows;
  if (!Array.isArray(rowsRaw) || rowsRaw.length > MAX_COST_ROWS) throw new Error('cost_projection_invalid');
  const rows = rowsRaw.map(parseRow);
  const totals = parseTotals(raw.totals);
  if (!sameTotals(totals, sumRows(rows))) throw new Error('cost_projection_totals_mismatch');
  const pricing = parsePricing(raw.pricing);
  if (pricing.status === 'unavailable'
    && (totals.actual_cost_usd !== null || rows.some(row => row.actual_cost_usd !== null))) {
    throw new Error('cost_projection_pricing_invalid');
  }
  const metadataRaw = exactObject(raw.metadata, [
    'source', 'generated_by', 'revision', 'report_digest', 'coverage', 'redacted',
  ]);
  if (metadataRaw.source !== 'runtime' || metadataRaw.generated_by !== 'runtime_usage_ledger' || metadataRaw.redacted !== true) {
    throw new Error('cost_projection_untrusted_source');
  }
  const confidence = exactObject(raw.confidence, ['actual', 'baseline', 'savings']);
  if (confidence.baseline !== 'blocked' || confidence.savings !== 'blocked') {
    throw new Error('cost_projection_invalid');
  }
  const metadata: CostProjectionMetadata = {
    source: 'runtime',
    generated_by: 'runtime_usage_ledger',
    revision: digest(metadataRaw.revision),
    report_digest: digest(metadataRaw.report_digest),
    coverage: parseCoverage(metadataRaw.coverage),
    redacted: true,
  };
  return {
    schema: COST_PROJECTION_SCHEMA,
    generated_at_epoch: epoch(raw.generated_at_epoch),
    query: parseQuery(raw.query),
    usage_revision: digest(raw.usage_revision),
    pricing,
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
