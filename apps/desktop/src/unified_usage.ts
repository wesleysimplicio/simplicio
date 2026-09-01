/** Runtime-owned, redacted usage contract. The Desktop validates and exports; it does not recompute usage. */
export const UNIFIED_USAGE_SCHEMA = 'simplicio.desktop-unified-usage/v1';
export const MAX_USAGE_ROWS = 500;
export const MAX_USAGE_EXPORT_BYTES = 64 * 1024;

export type UsageExecution = 'local' | 'remote';
export type UsageProvenance = 'provider-reported' | 'measured' | 'estimated' | 'unavailable';
export type UsageCoverage = 'complete' | 'partial' | 'no_data' | 'unavailable';

export interface UsageQuery {
  from_epoch?: number;
  to_epoch?: number;
  provider?: string;
  model?: string;
  host?: string;
  project_id?: string;
  session_id?: string;
}

export interface UsageRow {
  provider: string;
  model: string;
  host: string;
  project_id: string | null;
  session_id: string | null;
  execution: UsageExecution;
  input_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
  cost_usd: number | null;
  provenance: UsageProvenance;
  event_count: number;
}

export interface UsageTotals {
  event_count: number;
  input_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
  cost_usd: number | null;
}

export interface UsageCoverageInfo {
  status: UsageCoverage;
  missing_usage_events: number;
  unpriced_events: number;
  providers: string[];
  reason: string | null;
}

export interface UsageProjectionMetadata {
  source: 'runtime';
  generated_by: 'runtime_usage_ledger';
  generated_at_epoch: number;
  report_digest: string;
  pricing_version: string | null;
  pricing_sources: string[];
  coverage: UsageCoverageInfo;
  redacted: true;
}

export interface UnifiedUsageProjection {
  schema: typeof UNIFIED_USAGE_SCHEMA;
  generated_at_epoch: number;
  query: UsageQuery;
  rows: UsageRow[];
  totals: UsageTotals;
  metadata: UsageProjectionMetadata;
}

const PROVENANCES: UsageProvenance[] = [
  'provider-reported', 'measured', 'estimated', 'unavailable',
];
const EXECUTIONS: UsageExecution[] = ['local', 'remote'];
const COVERAGE: UsageCoverage[] = ['complete', 'partial', 'no_data', 'unavailable'];
const SENSITIVE_KEY = /(^|_)(prompt|cwd|path|argv|secret|password|credential|authorization|api_key|access_token|refresh_token|raw_payload|raw_event|home)(_|$)/i;

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('usage_projection_invalid');
  return value as Record<string, unknown>;
}

function text(value: unknown, max = 256): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > max || /[\u0000-\u001f\u007f]/.test(value)
    || /[\\/]/.test(value)) throw new Error('usage_projection_invalid');
  return value;
}

function nullableText(value: unknown): string | null {
  if (value === null) return null;
  return text(value);
}

function integer(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new Error('usage_projection_invalid');
  }
  return value;
}

function epoch(value: unknown): number {
  const result = integer(value);
  if (result > 4102444800) throw new Error('usage_projection_invalid');
  return result;
}

function money(value: unknown): number | null {
  if (value === null) return null;
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1_000_000_000) {
    throw new Error('usage_projection_invalid');
  }
  return value;
}

function digest(value: unknown): string {
  if (typeof value !== 'string' || !/^sha256:[a-f0-9]{64}$/.test(value)) {
    throw new Error('usage_projection_invalid');
  }
  return value;
}

function rejectSensitiveKeys(value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach(rejectSensitiveKeys);
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    if (SENSITIVE_KEY.test(key)) throw new Error('usage_projection_sensitive_field');
    rejectSensitiveKeys(child);
  }
}

function parseQuery(value: unknown): UsageQuery {
  if (value === undefined) return {};
  const raw = object(value);
  const query: UsageQuery = {};
  if (raw.from_epoch !== undefined) query.from_epoch = epoch(raw.from_epoch);
  if (raw.to_epoch !== undefined) query.to_epoch = epoch(raw.to_epoch);
  if (query.from_epoch !== undefined && query.to_epoch !== undefined && query.from_epoch >= query.to_epoch) {
    throw new Error('usage_projection_invalid');
  }
  if (raw.provider !== undefined) query.provider = text(raw.provider);
  if (raw.model !== undefined) query.model = text(raw.model);
  if (raw.host !== undefined) query.host = text(raw.host);
  if (raw.project_id !== undefined) query.project_id = text(raw.project_id);
  if (raw.session_id !== undefined) query.session_id = text(raw.session_id);
  return query;
}

function parseRow(value: unknown): UsageRow {
  const raw = object(value);
  const input = integer(raw.input_tokens);
  const cacheRead = integer(raw.cache_read_tokens);
  const cacheWrite = integer(raw.cache_write_tokens);
  const output = integer(raw.output_tokens);
  const reasoning = integer(raw.reasoning_tokens);
  const total = integer(raw.total_tokens);
  if (cacheRead > input || total !== input + output + reasoning) throw new Error('usage_projection_invalid');
  const provenance = text(raw.provenance);
  if (!PROVENANCES.includes(provenance as UsageProvenance)) throw new Error('usage_projection_invalid');
  const execution = text(raw.execution);
  if (!EXECUTIONS.includes(execution as UsageExecution)) throw new Error('usage_projection_invalid');
  return {
    provider: text(raw.provider),
    model: text(raw.model),
    host: text(raw.host),
    project_id: nullableText(raw.project_id),
    session_id: nullableText(raw.session_id),
    execution: execution as UsageExecution,
    input_tokens: input,
    cache_read_tokens: cacheRead,
    cache_write_tokens: cacheWrite,
    output_tokens: output,
    reasoning_tokens: reasoning,
    total_tokens: total,
    cost_usd: money(raw.cost_usd),
    provenance: provenance as UsageProvenance,
    event_count: integer(raw.event_count),
  };
}

function parseTotals(value: unknown): UsageTotals {
  const raw = object(value);
  const input = integer(raw.input_tokens);
  const cacheRead = integer(raw.cache_read_tokens);
  const cacheWrite = integer(raw.cache_write_tokens);
  const output = integer(raw.output_tokens);
  const reasoning = integer(raw.reasoning_tokens);
  const total = integer(raw.total_tokens);
  if (cacheRead > input || total !== input + output + reasoning) throw new Error('usage_projection_invalid');
  return {
    event_count: integer(raw.event_count),
    input_tokens: input,
    cache_read_tokens: cacheRead,
    cache_write_tokens: cacheWrite,
    output_tokens: output,
    reasoning_tokens: reasoning,
    total_tokens: total,
    cost_usd: money(raw.cost_usd),
  };
}

function parseCoverage(value: unknown): UsageCoverageInfo {
  const raw = object(value);
  const status = text(raw.status);
  if (!COVERAGE.includes(status as UsageCoverage)) throw new Error('usage_projection_invalid');
  const providers = Array.isArray(raw.providers) ? raw.providers.map((item) => text(item)) : [];
  return {
    status: status as UsageCoverage,
    missing_usage_events: integer(raw.missing_usage_events),
    unpriced_events: integer(raw.unpriced_events),
    providers,
    reason: raw.reason === null ? null : text(raw.reason),
  };
}

function sumRows(rows: UsageRow[]): UsageTotals {
  const totals: UsageTotals = {
    event_count: 0,
    input_tokens: 0,
    cache_read_tokens: 0,
    cache_write_tokens: 0,
    output_tokens: 0,
    reasoning_tokens: 0,
    total_tokens: 0,
    cost_usd: 0,
  };
  for (const row of rows) {
    totals.event_count += row.event_count;
    totals.input_tokens += row.input_tokens;
    totals.cache_read_tokens += row.cache_read_tokens;
    totals.cache_write_tokens += row.cache_write_tokens;
    totals.output_tokens += row.output_tokens;
    totals.reasoning_tokens += row.reasoning_tokens;
    totals.total_tokens += row.total_tokens;
    if (row.cost_usd === null) totals.cost_usd = null;
    else if (totals.cost_usd !== null) totals.cost_usd += row.cost_usd;
  }
  return totals;
}

function sameTotals(left: UsageTotals, right: UsageTotals): boolean {
  const sameNumbers = left.event_count === right.event_count
    && left.input_tokens === right.input_tokens
    && left.cache_read_tokens === right.cache_read_tokens
    && left.cache_write_tokens === right.cache_write_tokens
    && left.output_tokens === right.output_tokens
    && left.reasoning_tokens === right.reasoning_tokens
    && left.total_tokens === right.total_tokens;
  if (!sameNumbers) return false;
  if (left.cost_usd === null || right.cost_usd === null) return left.cost_usd === right.cost_usd;
  return Math.abs(left.cost_usd - right.cost_usd) < 0.00000001;
}

/** Parse only the versioned Runtime projection; unknown fields are intentionally discarded. */
export function parseUnifiedUsageProjection(value: unknown): UnifiedUsageProjection {
  rejectSensitiveKeys(value);
  const raw = object(value);
  if (raw.schema !== UNIFIED_USAGE_SCHEMA) throw new Error('usage_projection_invalid');
  const rowsRaw = raw.rows;
  if (!Array.isArray(rowsRaw) || rowsRaw.length > MAX_USAGE_ROWS) throw new Error('usage_projection_invalid');
  const rows = rowsRaw.map(parseRow);
  const query = parseQuery(raw.query);
  const totals = parseTotals(raw.totals);
  const metadataRaw = object(raw.metadata);
  if (metadataRaw.source !== 'runtime' || metadataRaw.generated_by !== 'runtime_usage_ledger'
    || metadataRaw.redacted !== true) throw new Error('usage_projection_untrusted_source');
  const metadata: UsageProjectionMetadata = {
    source: 'runtime',
    generated_by: 'runtime_usage_ledger',
    generated_at_epoch: epoch(metadataRaw.generated_at_epoch),
    report_digest: digest(metadataRaw.report_digest),
    pricing_version: metadataRaw.pricing_version === null ? null : text(metadataRaw.pricing_version),
    pricing_sources: Array.isArray(metadataRaw.pricing_sources)
      ? metadataRaw.pricing_sources.map((item) => text(item))
      : [],
    coverage: parseCoverage(metadataRaw.coverage),
    redacted: true,
  };
  const summed = sumRows(rows);
  if (!sameTotals(totals, summed)) throw new Error('usage_projection_totals_mismatch');
  if (rows.length === 0 && totals.event_count !== 0) throw new Error('usage_projection_totals_mismatch');
  if (metadata.coverage.status === 'no_data' && (rows.length !== 0 || totals.event_count !== 0)) {
    throw new Error('usage_projection_coverage_mismatch');
  }
  if (metadata.coverage.status === 'complete'
    && (metadata.coverage.missing_usage_events !== 0 || metadata.coverage.unpriced_events !== 0)) {
    throw new Error('usage_projection_coverage_mismatch');
  }
  if (metadata.coverage.status === 'partial'
    && metadata.coverage.missing_usage_events === 0 && metadata.coverage.unpriced_events === 0
    && rows.every((row) => row.provenance !== 'estimated' && row.provenance !== 'unavailable')) {
    throw new Error('usage_projection_coverage_mismatch');
  }
  if (metadata.coverage.status === 'unavailable' && rows.length !== 0) {
    throw new Error('usage_projection_coverage_mismatch');
  }
  return {
    schema: UNIFIED_USAGE_SCHEMA,
    generated_at_epoch: epoch(raw.generated_at_epoch),
    query,
    rows,
    totals,
    metadata,
  };
}

function csv(value: string | number | null): string {
  const textValue = value === null ? '' : String(value);
  return '"' + textValue.replace(/"/g, '""') + '"';
}

/** Export bounded, redacted Runtime data without recalculating any totals in the renderer. */
export function exportUnifiedUsageProjection(
  value: UnifiedUsageProjection,
  format: 'json' | 'csv',
): string {
  const projection = parseUnifiedUsageProjection(value);
  const output = format === 'json'
    ? JSON.stringify(projection)
    : [
      [
        'provider', 'model', 'host', 'project_id', 'session_id', 'execution',
        'input_tokens', 'cache_read_tokens', 'cache_write_tokens', 'output_tokens',
        'reasoning_tokens', 'total_tokens', 'cost_usd', 'provenance', 'event_count',
      ].join(','),
      ...projection.rows.map((row) => [
        row.provider, row.model, row.host, row.project_id, row.session_id, row.execution,
        row.input_tokens, row.cache_read_tokens, row.cache_write_tokens, row.output_tokens,
        row.reasoning_tokens, row.total_tokens, row.cost_usd, row.provenance, row.event_count,
      ].map(csv).join(',')),
    ].join('\n');
  if (new TextEncoder().encode(output).byteLength > MAX_USAGE_EXPORT_BYTES) {
    throw new Error('usage_export_too_large');
  }
  return output;
}
