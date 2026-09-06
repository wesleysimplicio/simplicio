export const SESSION_IDLE_FINALIZATION_SCHEMA = 'simplicio.session-idle-finalization/v1' as const;
export const IDLE_SESSION_TIMEOUT_MS = 15 * 60 * 1000;

export const SUPPORTED_PROVIDER_IDS = [
  'claude',
  'codex',
  'opencode',
  'grok',
  'vscode',
  'antigravity',
  'pi',
  'kiro',
  'cursor',
  'windsurf',
  'cline',
  'gemini',
  'hermes',
  'orca',
  'other',
] as const;

export type SupportedProviderId = typeof SUPPORTED_PROVIDER_IDS[number];
export type ProviderUsageMetric =
  | 'input_tokens'
  | 'output_tokens'
  | 'reasoning_tokens'
  | 'cache_read_tokens'
  | 'cache_write_tokens';
export type IdleUsageStatus = 'pending_provider_refresh' | 'complete' | 'unavailable';
export type ProviderUsageRefreshStatus =
  | 'complete'
  | 'partial'
  | 'no_new_events'
  | 'source_not_found'
  | 'source_unavailable'
  | 'adapter_not_bound';

export interface ProviderUsageReport {
  provider: string;
  adapter_id: string | null;
  status: ProviderUsageRefreshStatus;
  scope: 'scanned_local_sources';
  sources_discovered: number;
  sources_scanned: number;
  sources_skipped: number;
  events: number;
  matched_session_count: number;
  totals: Partial<Record<ProviderUsageMetric, number>>;
  missing_metrics: ProviderUsageMetric[];
  failure_codes: string[];
  reason?: string;
  redacted: true;
}

export interface IdleSessionUsage {
  status: IdleUsageStatus;
  metrics: ProviderUsageMetric[];
  scope?: 'scanned_local_sources';
  provider_reports?: ProviderUsageReport[];
  reason?: string;
}

export interface IdleSessionClosure {
  session_id: string;
  status: 'idle';
  updated_at: number;
}

export interface IdleSessionFinalization {
  schema: typeof SESSION_IDLE_FINALIZATION_SCHEMA;
  status: 'logical_closed';
  /** Stable Runtime key for exactly-once replay of the same closed sessions. */
  finalization_id?: string;
  profile_id: string;
  workspace_id: string;
  now_millis: number;
  idle_ms: number;
  closed_sessions: IdleSessionClosure[];
  usage: IdleSessionUsage;
  provider_processes_terminated: false;
  redacted: true;
}

const METRICS: ProviderUsageMetric[] = [
  'input_tokens',
  'output_tokens',
  'reasoning_tokens',
  'cache_read_tokens',
  'cache_write_tokens',
];
const MIN_IDLE_MS = 60 * 1000;
const MAX_IDLE_MS = 7 * 24 * 60 * 60 * 1000;
const SESSION_ID_MAX = 256;
const SCOPE_MAX = 256;

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('session_idle_finalization_invalid');
  }
  return value as Record<string, unknown>;
}

function boundedString(value: unknown, max: number, error = 'session_idle_finalization_invalid'): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > max) throw new Error(error);
  return value;
}

function safeInteger(value: unknown, error = 'session_idle_finalization_invalid'): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new Error(error);
  return value;
}

function usageStatus(value: unknown): IdleUsageStatus {
  if (value === 'pending_provider_refresh' || value === 'complete' || value === 'unavailable') {
    return value;
  }
  throw new Error('session_idle_finalization_invalid');
}

function parseMetrics(value: unknown): ProviderUsageMetric[] {
  if (!Array.isArray(value) || value.length !== METRICS.length) {
    throw new Error('session_idle_finalization_invalid');
  }
  const values = value.filter((metric): metric is ProviderUsageMetric =>
    typeof metric === 'string' && (METRICS as string[]).includes(metric),
  );
  if (values.length !== METRICS.length || new Set(values).size !== METRICS.length) {
    throw new Error('session_idle_finalization_invalid');
  }
  return METRICS.slice();
}

const PROVIDER_USAGE_STATUSES: ProviderUsageRefreshStatus[] = [
  'complete',
  'partial',
  'no_new_events',
  'source_not_found',
  'source_unavailable',
  'adapter_not_bound',
];

function boundedCount(value: unknown, maximum: number): number {
  const count = safeInteger(value);
  if (count > maximum) throw new Error('session_idle_finalization_invalid');
  return count;
}

function parseProviderTotals(value: unknown): Partial<Record<ProviderUsageMetric, number>> {
  const raw = record(value);
  const totals: Partial<Record<ProviderUsageMetric, number>> = {};
  for (const [key, metricValue] of Object.entries(raw)) {
    if (!(METRICS as string[]).includes(key)) throw new Error('session_idle_finalization_invalid');
    totals[key as ProviderUsageMetric] = boundedCount(metricValue, Number.MAX_SAFE_INTEGER);
  }
  return totals;
}

function parseMissingMetrics(value: unknown): ProviderUsageMetric[] {
  if (!Array.isArray(value) || value.length > METRICS.length) {
    throw new Error('session_idle_finalization_invalid');
  }
  const metrics = value.filter((metric): metric is ProviderUsageMetric =>
    typeof metric === 'string' && (METRICS as string[]).includes(metric),
  );
  if (metrics.length !== value.length || new Set(metrics).size !== metrics.length) {
    throw new Error('session_idle_finalization_invalid');
  }
  return metrics;
}

function parseFailureCodes(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > 16) throw new Error('session_idle_finalization_invalid');
  return value.map((code) => boundedString(code, 64));
}

function parseProviderReport(value: unknown): ProviderUsageReport {
  const raw = record(value);
  const status = raw.status;
  if (!PROVIDER_USAGE_STATUSES.includes(status as ProviderUsageRefreshStatus)) {
    throw new Error('session_idle_finalization_invalid');
  }
  const adapter = raw.adapter_id === null ? null : boundedString(raw.adapter_id, 128);
  if (raw.scope !== 'scanned_local_sources' || raw.redacted !== true) {
    throw new Error('session_idle_finalization_invalid');
  }
  const report: ProviderUsageReport = {
    provider: boundedString(raw.provider, 64),
    adapter_id: adapter,
    status: status as ProviderUsageRefreshStatus,
    scope: 'scanned_local_sources',
    sources_discovered: boundedCount(raw.sources_discovered, 1024),
    sources_scanned: boundedCount(raw.sources_scanned, 1024),
    sources_skipped: boundedCount(raw.sources_skipped, 1024),
    events: boundedCount(raw.events, 10_000),
    matched_session_count: boundedCount(raw.matched_session_count, 256),
    totals: parseProviderTotals(raw.totals),
    missing_metrics: parseMissingMetrics(raw.missing_metrics),
    failure_codes: parseFailureCodes(raw.failure_codes),
    redacted: true,
  };
  if (raw.reason !== undefined) report.reason = boundedString(raw.reason, 128);
  return report;
}

function parseClosure(value: unknown): IdleSessionClosure {
  const raw = record(value);
  return {
    session_id: boundedString(raw.session_id, SESSION_ID_MAX),
    status: raw.status === 'idle' ? 'idle' : (() => { throw new Error('session_idle_finalization_invalid'); })(),
    updated_at: safeInteger(raw.updated_at),
  };
}

/**
 * Parse only the redacted Runtime receipt. A pending provider refresh is
 * explicit: missing provider telemetry is never represented by zeroes.
 */
export function parseIdleSessionFinalization(value: unknown): IdleSessionFinalization {
  const raw = record(value);
  if (raw.schema !== SESSION_IDLE_FINALIZATION_SCHEMA
    || raw.status !== 'logical_closed'
    || raw.provider_processes_terminated !== false
    || raw.redacted !== true) {
    throw new Error('session_idle_finalization_invalid');
  }
  const profileId = boundedString(raw.profile_id, SCOPE_MAX);
  const workspaceId = boundedString(raw.workspace_id, SCOPE_MAX);
  const finalizationId = raw.finalization_id === undefined
    ? undefined
    : boundedString(raw.finalization_id, 128);
  const nowMillis = safeInteger(raw.now_millis);
  const idleMs = safeInteger(raw.idle_ms);
  if (idleMs < MIN_IDLE_MS || idleMs > MAX_IDLE_MS) throw new Error('session_idle_finalization_invalid');
  const closedRaw = raw.closed_sessions;
  if (!Array.isArray(closedRaw) || closedRaw.length > 256) throw new Error('session_idle_finalization_invalid');
  const closedSessions = closedRaw.map(parseClosure);
  const usageRaw = record(raw.usage);
  const usage: IdleSessionUsage = {
    status: usageStatus(usageRaw.status),
    metrics: parseMetrics(usageRaw.metrics),
  };
  if (usageRaw.scope !== undefined) {
    if (usageRaw.scope !== 'scanned_local_sources') throw new Error('session_idle_finalization_invalid');
    usage.scope = 'scanned_local_sources';
  }
  if (usageRaw.provider_reports !== undefined) {
    if (!Array.isArray(usageRaw.provider_reports) || usageRaw.provider_reports.length > 32) {
      throw new Error('session_idle_finalization_invalid');
    }
    usage.provider_reports = usageRaw.provider_reports.map(parseProviderReport);
  }
  if (usageRaw.reason !== undefined) usage.reason = boundedString(usageRaw.reason, 128);
  return {
    schema: SESSION_IDLE_FINALIZATION_SCHEMA,
    status: 'logical_closed',
    ...(finalizationId === undefined ? {} : { finalization_id: finalizationId }),
    profile_id: profileId,
    workspace_id: workspaceId,
    now_millis: nowMillis,
    idle_ms: idleMs,
    closed_sessions: closedSessions,
    usage,
    provider_processes_terminated: false,
    redacted: true,
  };
}

/** Keep the policy boundary testable without opening or terminating provider processes. */
export function shouldCloseIdleSession(
  lastActivityEpochMs: number,
  nowEpochMs: number,
  idleMs = IDLE_SESSION_TIMEOUT_MS,
  activeRequest = false,
): boolean {
  if (activeRequest || !Number.isSafeInteger(lastActivityEpochMs)
    || !Number.isSafeInteger(nowEpochMs) || !Number.isSafeInteger(idleMs)
    || lastActivityEpochMs < 0 || nowEpochMs < lastActivityEpochMs
    || idleMs < MIN_IDLE_MS || idleMs > MAX_IDLE_MS) {
    return false;
  }
  return nowEpochMs - lastActivityEpochMs >= idleMs;
}

export function isSupportedProviderId(value: string): value is SupportedProviderId {
  return (SUPPORTED_PROVIDER_IDS as readonly string[]).includes(value.trim().toLowerCase());
}
