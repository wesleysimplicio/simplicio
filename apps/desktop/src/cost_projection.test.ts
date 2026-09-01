import { describe, expect, it } from 'vitest';
import { exportCostProjection, parseCostProjection, type CostProjection } from './cost_projection';

const digestA = 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

const fixture: CostProjection = {
  schema: 'simplicio.desktop-cost-economy/v1',
  generated_at_epoch: 1700000100,
  query: {
    window: 'custom',
    from_epoch: 1700000000,
    to_epoch: 1700000100,
    provider: 'openai',
    model: 'gpt-5',
    host: 'codex',
    project_id: 'project-alpha',
    session_id: 'session-1',
  },
  periods: [{
    window: 'custom',
    from_epoch: 1700000000,
    to_epoch: 1700000100,
    totals: {
      event_count: 2,
      actual_tokens: null,
      baseline_tokens: null,
      saved_tokens: null,
      actual_cost_usd: null,
      baseline_cost_usd: null,
      saved_cost_usd: null,
    },
  }],
  breakdown: [
    {
      provider: 'openai',
      model: 'gpt-5',
      host: 'codex',
      project_id: 'project-alpha',
      session_id: 'session-1',
      execution: 'remote',
      event_count: 1,
      actual_tokens: 150,
      baseline_tokens: 200,
      saved_tokens: 50,
      actual_cost_usd: 0.02,
      baseline_cost_usd: 0.03,
      saved_cost_usd: 0.01,
      provenance: 'provider-reported',
    },
    {
      provider: 'local-provider',
      model: 'local-model',
      host: 'claude',
      project_id: null,
      session_id: null,
      execution: 'local',
      event_count: 1,
      actual_tokens: null,
      baseline_tokens: null,
      saved_tokens: null,
      actual_cost_usd: null,
      baseline_cost_usd: null,
      saved_cost_usd: null,
      provenance: 'unavailable',
    },
  ],
  totals: {
    event_count: 2,
    actual_tokens: null,
    baseline_tokens: null,
    saved_tokens: null,
    actual_cost_usd: null,
    baseline_cost_usd: null,
    saved_cost_usd: null,
  },
  metadata: {
    source: 'runtime',
    generated_by: 'runtime_usage_ledger',
    generated_at_epoch: 1700000100,
    report_digest: digestA,
    pricing: {
      status: 'known',
      version: 'pricing-2026-01',
      sources: ['runtime-pricing-ledger'],
    },
    coverage: {
      status: 'partial',
      missing_usage_events: 0,
      unpriced_events: 1,
      conflicts: 0,
      reason: 'one provider has no pricing',
    },
    redacted: true,
  },
};

describe('Runtime cost/economy contract', () => {
  it('preserves periods, every filter, provenance, and unknown values', () => {
    const parsed = parseCostProjection(fixture);
    expect(parsed.query).toEqual(fixture.query);
    expect(parsed.periods[0].window).toBe('custom');
    expect(parsed.breakdown[1].actual_cost_usd).toBeNull();
    expect(parsed.metadata.coverage.unpriced_events).toBe(1);
  });

  it('requires Runtime-proved savings instead of recomputing or inventing it', () => {
    expect(() => parseCostProjection({
      ...fixture,
      breakdown: [{
        ...fixture.breakdown[0],
        saved_cost_usd: 0,
      }, fixture.breakdown[1]],
    })).toThrow('cost_projection_savings_mismatch');
  });

  it('rejects preview, paths, and sensitive fields', () => {
    expect(() => parseCostProjection({ ...fixture, preview: true })).toThrow('cost_projection_sensitive_field');
    expect(() => parseCostProjection({
      ...fixture,
      breakdown: [{ ...fixture.breakdown[0], path: '/private/project' }, fixture.breakdown[1]],
    })).toThrow('cost_projection_sensitive_field');
  });

  it('exports bounded JSON and CSV with no raw prompts or paths', () => {
    const json = exportCostProjection(fixture, 'json');
    const csv = exportCostProjection(fixture, 'csv');
    expect(json).toContain('simplicio.desktop-cost-economy/v1');
    expect(csv.split('\n')[0]).toContain('actual_cost_usd');
    expect(csv).toContain('provider-reported');
    expect(csv).not.toContain('private');
  });
});
