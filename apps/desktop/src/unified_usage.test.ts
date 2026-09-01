import { describe, expect, it } from 'vitest';
import {
  exportUnifiedUsageProjection,
  parseUnifiedUsageProjection,
  type UnifiedUsageProjection,
} from './unified_usage';

const fixture: UnifiedUsageProjection = {
  schema: 'simplicio.desktop-unified-usage/v1',
  generated_at_epoch: 1700000100,
  query: {
    from_epoch: 1700000000,
    to_epoch: 1700000100,
    provider: 'openai',
    model: 'gpt-5',
    host: 'codex',
    project_id: 'project-alpha',
    session_id: 'session-1',
  },
  rows: [
    {
      provider: 'openai',
      model: 'gpt-5',
      host: 'codex',
      project_id: 'project-alpha',
      session_id: 'session-1',
      execution: 'remote',
      input_tokens: 100,
      cache_read_tokens: 20,
      cache_write_tokens: 5,
      output_tokens: 40,
      reasoning_tokens: 10,
      total_tokens: 150,
      cost_usd: 0.02,
      provenance: 'provider-reported',
      event_count: 1,
    },
    {
      provider: 'local-provider',
      model: 'local-model',
      host: 'claude',
      project_id: null,
      session_id: null,
      execution: 'local',
      input_tokens: 30,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      output_tokens: 5,
      reasoning_tokens: 0,
      total_tokens: 35,
      cost_usd: null,
      provenance: 'unavailable',
      event_count: 1,
    },
  ],
  totals: {
    event_count: 2,
    input_tokens: 130,
    cache_read_tokens: 20,
    cache_write_tokens: 5,
    output_tokens: 45,
    reasoning_tokens: 10,
    total_tokens: 185,
    cost_usd: null,
  },
  metadata: {
    source: 'runtime',
    generated_by: 'runtime_usage_ledger',
    generated_at_epoch: 1700000100,
    report_digest: 'sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
    pricing_version: 'pricing-2026-01',
    pricing_sources: ['runtime-pricing-ledger'],
    coverage: {
      status: 'partial',
      missing_usage_events: 1,
      unpriced_events: 1,
      providers: ['openai', 'local-provider'],
      reason: 'one provider did not report cost',
    },
    redacted: true,
  },
};

describe('unified usage Runtime contract', () => {
  it('preserves every supported filter dimension and redacted accounting field', () => {
    const parsed = parseUnifiedUsageProjection(fixture);
    expect(parsed.query).toEqual(fixture.query);
    expect(parsed.totals.total_tokens).toBe(185);
    expect(parsed.rows[0].execution).toBe('remote');
    expect(parsed.rows[1].provenance).toBe('unavailable');
  });

  it('fails closed when a renderer-facing payload contains raw prompt data', () => {
    expect(() => parseUnifiedUsageProjection({
      ...fixture,
      rows: [{ ...fixture.rows[0], prompt: 'do not export this' }],
    })).toThrow('usage_projection_sensitive_field');
  });

  it('fails closed on inconsistent totals instead of recomputing them', () => {
    expect(() => parseUnifiedUsageProjection({
      ...fixture,
      totals: { ...fixture.totals, total_tokens: 999 },
    })).toThrow('usage_projection_totals_mismatch');
  });

  it('exports bounded JSON and CSV without raw IDs or sensitive fields', () => {
    const json = exportUnifiedUsageProjection(fixture, 'json');
    const csv = exportUnifiedUsageProjection(fixture, 'csv');
    expect(json).toContain('simplicio.desktop-unified-usage/v1');
    expect(json).not.toContain('do not export');
    expect(csv.split('\n')[0]).toContain('input_tokens');
    expect(csv).toContain('provider-reported');
    expect(csv).not.toContain('prompt');
  });
});
