import { describe, expect, it } from 'vitest';
import {
  IDLE_SESSION_TIMEOUT_MS,
  parseIdleSessionFinalization,
  shouldCloseIdleSession,
  type IdleSessionFinalization,
} from './session_idle';

const baseReceipt: IdleSessionFinalization = {
  schema: 'simplicio.session-idle-finalization/v1',
  status: 'logical_closed',
  profile_id: 'default',
  workspace_id: '/workspace',
  now_millis: 1_000_000,
  idle_ms: IDLE_SESSION_TIMEOUT_MS,
  closed_sessions: [{
    session_id: 'session-1',
    status: 'idle',
    updated_at: 10_000,
  }],
  usage: {
    status: 'pending_provider_refresh',
    metrics: [
      'input_tokens',
      'output_tokens',
      'reasoning_tokens',
      'cache_read_tokens',
      'cache_write_tokens',
    ],
  },
  provider_processes_terminated: false,
  redacted: true,
};

describe('logical idle-session policy', () => {
  it('closes exactly at 15 minutes, not one second before', () => {
    expect(shouldCloseIdleSession(0, IDLE_SESSION_TIMEOUT_MS - 1)).toBe(false);
    expect(shouldCloseIdleSession(0, IDLE_SESSION_TIMEOUT_MS)).toBe(true);
  });

  it('does not close a session while a request is active or when the clock moves backwards', () => {
    expect(shouldCloseIdleSession(0, IDLE_SESSION_TIMEOUT_MS, IDLE_SESSION_TIMEOUT_MS, true)).toBe(false);
    expect(shouldCloseIdleSession(10_000, 9_999)).toBe(false);
  });

  it('preserves the Runtime finalization id for replay and rejects oversized ids', () => {
    const parsed = parseIdleSessionFinalization({
      ...baseReceipt,
      finalization_id: 'sha256:receipt-1',
    });
    expect(parsed.finalization_id).toBe('sha256:receipt-1');
    expect(() => parseIdleSessionFinalization({
      ...baseReceipt,
      finalization_id: 'x'.repeat(129),
    })).toThrow('session_idle_finalization_invalid');
  });

  it('keeps provider refresh pending instead of inventing zero token values', () => {
    const parsed = parseIdleSessionFinalization(baseReceipt);
    expect(parsed.usage.status).toBe('pending_provider_refresh');
    expect(JSON.stringify(parsed)).not.toMatch(/0 tokens|token_usage/);
  });

  it('exposes bounded provider refresh totals without leaking source paths', () => {
    const parsed = parseIdleSessionFinalization({
      ...baseReceipt,
      usage: {
        ...baseReceipt.usage,
        status: 'complete',
        scope: 'scanned_local_sources',
        provider_reports: [{
          provider: 'codex',
          adapter_id: 'simplicio.codex-usage-adapter/v1',
          status: 'complete',
          scope: 'scanned_local_sources',
          sources_discovered: 1,
          sources_scanned: 1,
          sources_skipped: 0,
          events: 1,
          matched_session_count: 1,
          totals: { input_tokens: 4, output_tokens: 2 },
          missing_metrics: ['reasoning_tokens', 'cache_read_tokens', 'cache_write_tokens'],
          failure_codes: [],
          redacted: true,
        }],
      },
    });
    expect(parsed.usage.provider_reports?.[0].totals.input_tokens).toBe(4);
    expect(JSON.stringify(parsed)).not.toContain('jsonl');
  });

  it('fails closed when the receipt omits one required usage metric', () => {
    const invalid = {
      ...baseReceipt,
      usage: {
        ...baseReceipt.usage,
        metrics: baseReceipt.usage.metrics.slice(0, -1),
      },
    };
    expect(() => parseIdleSessionFinalization(invalid)).toThrow('session_idle_finalization_invalid');
  });
});

function boundUsage() {
  return {
    schema: 'simplicio.bound-session-usage/v1',
    scope: 'bound_runtime_sessions', redacted: true, network_calls: 0, provider_processes_terminated: false,
    scan: { provider_reports: [{ failure_codes: [] as string[] }], redacted: true, network_calls: 0 },
    session_reports: [{
      session_id: 'session-1', status: 'partial', binding_count: 1, events: 2,
      totals: { input_tokens: 12, output_tokens: null, reasoning_tokens: null, cache_read_tokens: null, cache_write_tokens: null },
      known_totals: { input_tokens: 12, output_tokens: 3 },
      provenance: 'provider_reported', redacted: true,
    }],
  };
}

describe('bound Runtime session usage', () => {
  it('keeps unknown totals separate from known subtotals', () => {
    const receipt = parseIdleSessionFinalization({ ...baseReceipt, session_usage: boundUsage() });
    expect(receipt.session_usage?.session_reports[0].totals.output_tokens).toBeNull();
    expect(receipt.session_usage?.session_reports[0].known_totals.output_tokens).toBe(3);
    expect(receipt.session_usage?.collection_partial).toBe(false);
  });
  it('exposes a bounded collection failure', () => {
    const usage = boundUsage();
    usage.scan.provider_reports[0].failure_codes = ['source_bound_reached'];
    expect(parseIdleSessionFinalization({ ...baseReceipt, session_usage: usage })
      .session_usage?.collection_partial).toBe(true);
  });
  it('rejects another session and duplicate session projections', () => {
    const usage = boundUsage();
    usage.session_reports[0].session_id = 'another-session';
    expect(() => parseIdleSessionFinalization({ ...baseReceipt, session_usage: usage })).toThrow();
    usage.session_reports[0].session_id = 'session-1';
    usage.session_reports.push(usage.session_reports[0]);
    expect(() => parseIdleSessionFinalization({ ...baseReceipt, session_usage: usage })).toThrow();
  });
  it('rejects missing metrics and inconsistent known totals', () => {
    const usage = boundUsage();
    usage.session_reports[0].known_totals.input_tokens = 99;
    expect(() => parseIdleSessionFinalization({ ...baseReceipt, session_usage: usage })).toThrow();
    usage.session_reports[0].known_totals.input_tokens = 12;
    expect(() => parseIdleSessionFinalization({ ...baseReceipt, session_usage: {
      ...usage, session_reports: [{ ...usage.session_reports[0], totals: {} }],
    } })).toThrow();
  });
});
