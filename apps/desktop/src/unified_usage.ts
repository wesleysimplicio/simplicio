/** Runtime-owned, redacted usage contract. The Desktop validates and exports; it does not recompute usage. */
export const UNIFIED_USAGE_SCHEMA = 'simplicio.desktop-unified-usage/v1';
export const MAX_USAGE_ROWS = 500;
export const MAX_USAGE_EXPORT_BYTES = 64 * 1024;

export type UsageExecution = 'local' | 'remote';
export type UsageProvenance = 'provider-reported' | 'measured' | 'estimated' | 'unavailable';
export type UsageCoverage = 'complete' | 'partial' | 'no_data' | 'unavailable';
export type ReasoningSemantics = 'separate' | 'included_in_output' | 'unknown';
export type UsageSourceCompleteness = 'complete' | 'partial';

export interface UsageQuery {
  from_epoch?: number;
  to_epoch?: number;
  provider?: string;
  model?: string;
  host?: string;
  project_id?: string;
  session_id?: string;
}

export type UnifiedUsagePeriod = 'today' | '7d' | '1m' | '3m' | '6m' | '12m' | 'custom';

export interface UnifiedUsageQueryInput {
  period: UnifiedUsagePeriod;
  now_epoch: number;
  selected_range?: { from_epoch: number; to_epoch: number };
  custom_range?: { from_epoch: number; to_epoch: number };
  provider?: string;
  model?: string;
  host?: string;
  session_id?: string;
}

/** Logical cancellation guard for renderer requests; late native replies cannot repopulate stale filters. */
export class UnifiedUsageRequestGuard {
  private generation = 0;

  begin(): number {
    this.generation += 1;
    return this.generation;
  }

  invalidate(): void {
    this.generation += 1;
  }

  isCurrent(request: number): boolean {
    return request === this.generation;
  }
}

const PERIOD_DAYS: Record<Exclude<UnifiedUsagePeriod, 'custom'>, number> = {
  today: 1,
  '7d': 7,
  '1m': 30,
  '3m': 90,
  '6m': 180,
  '12m': 365,
};

function queryEpoch(value: number): number {
  if (!Number.isSafeInteger(value) || value < 0 || value > 4_102_444_800) {
    throw new Error('unified_usage_query_invalid');
  }
  return value;
}

function queryFilter(value: string | undefined): string | undefined {
  const normalized = value?.trim();
  if (!normalized) return undefined;
  if (normalized.length > 256 || /[\u0000-\u001f\u007f]/.test(normalized)) {
    throw new Error('unified_usage_query_invalid');
  }
  return normalized;
}

/** Build only Runtime-supported filters; project paths stay on the native transport boundary. */
export function buildUnifiedUsageQuery(input: UnifiedUsageQueryInput): UsageQuery {
  const range = input.selected_range
    ?? (input.period === 'custom'
      ? input.custom_range
      : {
        from_epoch: queryEpoch(input.now_epoch) - PERIOD_DAYS[input.period] * 86_400,
        to_epoch: queryEpoch(input.now_epoch),
      });
  if (!range) throw new Error('unified_usage_query_invalid');
  const fromEpoch = queryEpoch(range.from_epoch);
  const toEpoch = queryEpoch(range.to_epoch);
  if (fromEpoch >= toEpoch) throw new Error('unified_usage_query_invalid');

  const query: UsageQuery = { from_epoch: fromEpoch, to_epoch: toEpoch };
  const provider = queryFilter(input.provider);
  const model = queryFilter(input.model);
  const host = queryFilter(input.host);
  const sessionId = queryFilter(input.session_id);
  if (provider !== undefined) query.provider = provider;
  if (model !== undefined) query.model = model;
  if (host !== undefined) query.host = host;
  if (sessionId !== undefined) query.session_id = sessionId;
  return query;
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
  reported_output_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
  cost_usd: number | null;
  provenance: UsageProvenance;
  reasoning_semantics: ReasoningSemantics;
  reasoning_semantics_provenance: UsageProvenance;
  reasoning_semantics_reason: string | null;
  event_count: number;
  source_completeness: UsageSourceCompleteness;
  incomplete_events: number;
  missing_usage_events: number;
  unpriced_events: number;
  metric_provenance: Record<string, UsageProvenance[]>;
  missing_metrics: Record<string, number>;
}

export interface UsageTotals {
  event_count: number;
  input_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  reported_output_tokens: number;
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
  revision: string;
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

/** Remote account quotas are intentionally absent from Runtime contract v1. */
export const UNIFIED_USAGE_ACCOUNT_LIMITS = Object.freeze({
  status: 'unavailable' as const,
  limit: null,
  remaining: null,
  reset_at_epoch: null,
  reason: 'not_in_runtime_contract_v1' as const,
});

export function unifiedUsageState(projection: UnifiedUsageProjection): {
  showMetrics: boolean;
  message: string;
} {
  const { coverage } = projection.metadata;
  if (coverage.status === 'no_data') {
    return { showMetrics: false, message: 'Nenhum evento corresponde aos filtros; consumo não foi presumido como zero.' };
  }
  if (coverage.status === 'unavailable') {
    return { showMetrics: false, message: 'Uso indisponível; nenhum total foi presumido.' };
  }
  if (coverage.status === 'partial') {
    return { showMetrics: true, message: `Cobertura parcial: ${coverage.missing_usage_events} evento(s) ausente(s) e ${coverage.unpriced_events} sem preço.` };
  }
  return { showMetrics: true, message: 'Cobertura completa para os eventos retornados pelo Runtime.' };
}

const PROVENANCES: UsageProvenance[] = [
  'provider-reported', 'measured', 'estimated', 'unavailable',
];
const EXECUTIONS: UsageExecution[] = ['local', 'remote'];
const COVERAGE: UsageCoverage[] = ['complete', 'partial', 'no_data', 'unavailable'];
const REASONING_SEMANTICS: ReasoningSemantics[] = ['separate', 'included_in_output', 'unknown'];
const SOURCE_COMPLETENESS: UsageSourceCompleteness[] = ['complete', 'partial'];
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

function parseMetricProvenance(value: unknown): Record<string, UsageProvenance[]> {
  const raw = object(value);
  const parsed: Record<string, UsageProvenance[]> = {};
  if (Object.keys(raw).length > 13) throw new Error('usage_projection_invalid');
  for (const [metric, entries] of Object.entries(raw)) {
    if (!/^[a-z][a-z0-9_]{0,63}$/.test(metric) || !Array.isArray(entries) || entries.length > 4) {
      throw new Error('usage_projection_invalid');
    }
    const provenances = entries.map((entry) => text(entry) as UsageProvenance);
    if (provenances.some((entry) => !PROVENANCES.includes(entry))) throw new Error('usage_projection_invalid');
    parsed[metric] = provenances;
  }
  return parsed;
}

function parseMissingMetrics(value: unknown): Record<string, number> {
  const raw = object(value);
  const parsed: Record<string, number> = {};
  if (Object.keys(raw).length > 13) throw new Error('usage_projection_invalid');
  for (const [metric, count] of Object.entries(raw)) {
    if (!/^[a-z][a-z0-9_]{0,63}$/.test(metric)) throw new Error('usage_projection_invalid');
    parsed[metric] = integer(count);
  }
  return parsed;
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
  const reportedOutput = integer(raw.reported_output_tokens);
  const output = integer(raw.output_tokens);
  const reasoning = integer(raw.reasoning_tokens);
  const total = integer(raw.total_tokens);
  if (cacheRead > input || total !== input + output + reasoning) throw new Error('usage_projection_invalid');
  const provenance = text(raw.provenance);
  if (!PROVENANCES.includes(provenance as UsageProvenance)) throw new Error('usage_projection_invalid');
  const execution = text(raw.execution);
  if (!EXECUTIONS.includes(execution as UsageExecution)) throw new Error('usage_projection_invalid');
  const reasoningSemantics = text(raw.reasoning_semantics);
  const reasoningSemanticsProvenance = text(raw.reasoning_semantics_provenance);
  const sourceCompleteness = text(raw.source_completeness);
  if (!REASONING_SEMANTICS.includes(reasoningSemantics as ReasoningSemantics)) throw new Error('usage_projection_invalid');
  if (!PROVENANCES.includes(reasoningSemanticsProvenance as UsageProvenance)) throw new Error('usage_projection_invalid');
  if (!SOURCE_COMPLETENESS.includes(sourceCompleteness as UsageSourceCompleteness)) throw new Error('usage_projection_invalid');
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
    reported_output_tokens: reportedOutput,
    output_tokens: output,
    reasoning_tokens: reasoning,
    total_tokens: total,
    cost_usd: money(raw.cost_usd),
    provenance: provenance as UsageProvenance,
    reasoning_semantics: reasoningSemantics as ReasoningSemantics,
    reasoning_semantics_provenance: reasoningSemanticsProvenance as UsageProvenance,
    reasoning_semantics_reason: nullableText(raw.reasoning_semantics_reason),
    event_count: integer(raw.event_count),
    source_completeness: sourceCompleteness as UsageSourceCompleteness,
    incomplete_events: integer(raw.incomplete_events),
    missing_usage_events: integer(raw.missing_usage_events),
    unpriced_events: integer(raw.unpriced_events),
    metric_provenance: parseMetricProvenance(raw.metric_provenance),
    missing_metrics: parseMissingMetrics(raw.missing_metrics),
  };
}

function parseTotals(value: unknown): UsageTotals {
  const raw = object(value);
  const input = integer(raw.input_tokens);
  const cacheRead = integer(raw.cache_read_tokens);
  const cacheWrite = integer(raw.cache_write_tokens);
  const reportedOutput = integer(raw.reported_output_tokens);
  const output = integer(raw.output_tokens);
  const reasoning = integer(raw.reasoning_tokens);
  const total = integer(raw.total_tokens);
  if (cacheRead > input || total !== input + output + reasoning) throw new Error('usage_projection_invalid');
  return {
    event_count: integer(raw.event_count),
    input_tokens: input,
    cache_read_tokens: cacheRead,
    cache_write_tokens: cacheWrite,
    reported_output_tokens: reportedOutput,
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
    revision: digest(metadataRaw.revision),
    pricing_version: metadataRaw.pricing_version === null ? null : text(metadataRaw.pricing_version),
    pricing_sources: Array.isArray(metadataRaw.pricing_sources)
      ? metadataRaw.pricing_sources.map((item) => text(item))
      : [],
    coverage: parseCoverage(metadataRaw.coverage),
    redacted: true,
  };
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
          'input_tokens', 'cache_read_tokens', 'cache_write_tokens', 'reported_output_tokens',
          'output_tokens', 'reasoning_tokens', 'total_tokens', 'cost_usd', 'provenance',
          'reasoning_semantics', 'reasoning_semantics_provenance', 'source_completeness',
          'incomplete_events', 'missing_usage_events', 'unpriced_events', 'event_count',
        ].join(','),
        ...projection.rows.map((row) => [
          row.provider, row.model, row.host, row.project_id, row.session_id, row.execution,
          row.input_tokens, row.cache_read_tokens, row.cache_write_tokens, row.reported_output_tokens,
          row.output_tokens, row.reasoning_tokens, row.total_tokens, row.cost_usd, row.provenance,
          row.reasoning_semantics, row.reasoning_semantics_provenance, row.source_completeness,
          row.incomplete_events, row.missing_usage_events, row.unpriced_events, row.event_count,
        ].map(csv).join(',')),
    ].join('\n');
  if (new TextEncoder().encode(output).byteLength > MAX_USAGE_EXPORT_BYTES) {
    throw new Error('usage_export_too_large');
  }
  return output;
}
