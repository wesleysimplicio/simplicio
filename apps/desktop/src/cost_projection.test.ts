import { describe, expect, it } from 'vitest';
import { exportCostProjection, parseCostProjection, type CostProjection } from './cost_projection';

const digestA = 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const digestB = 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';

const fixture: CostProjection = {
  schema: 'simplicio.desktop-cost-projection/v1',
  generated_at_epoch: 1700000100,
  query: { provider: 'openai', session_id: digestB },
  usage_revision: digestA,
  pricing: {
    status: 'known',
    identity: digestB,
    version: 'pricing-2026-01',
    versions: ['pricing-2026-01'],
    sources: ['provider-reported'],
  },
  baseline: {
    identity_status: 'known',
    versions: ['baseline-2026-01'],
    methods: ['provider-list-price'],
    values_status: 'unavailable',
    reason: 'baseline_values_not_recorded',
  },
  confidence: { actual: 'blocked', baseline: 'blocked', savings: 'blocked' },
  rows: [
    {
      provider: 'openai', model: 'gpt-5', host: 'codex',
      project_id: digestA, session_id: digestB, execution: 'remote', event_count: 1,
      actual_tokens: 150, actual_cost_usd: 0.02,
      baseline_tokens: null, baseline_cost_usd: null, saved_tokens: null, saved_cost_usd: null,
      state: 'provider-reported', confidence: 'high', reason: null,
    },
    {
      provider: 'local-provider', model: 'local-model', host: 'claude',
      project_id: digestA, session_id: digestB, execution: 'local', event_count: 1,
      actual_tokens: null, actual_cost_usd: null,
      baseline_tokens: null, baseline_cost_usd: null, saved_tokens: null, saved_cost_usd: null,
      state: 'unavailable', confidence: 'blocked', reason: 'usage_or_pricing_incomplete',
    },
  ],
  totals: {
    event_count: 2,
    actual_tokens: null, actual_cost_usd: null,
    baseline_tokens: null, baseline_cost_usd: null, saved_tokens: null, saved_cost_usd: null,
  },
  metadata: {
    source: 'runtime', generated_by: 'runtime_usage_ledger', revision: digestB, report_digest: digestA,
    coverage: {
      status: 'partial', missing_usage_events: 0, unpriced_events: 1,
      providers: ['openai'], reason: 'one provider has no pricing',
    },
    redacted: true,
  },
};

describe('Runtime desktop cost projection contract', () => {
  it('preserves the Runtime query, rows, provenance, and unknown values', () => {
    const parsed = parseCostProjection(fixture);
    expect(parsed.query).toEqual(fixture.query);
    expect(parsed.rows[1].actual_cost_usd).toBeNull();
    expect(parsed.metadata.coverage.unpriced_events).toBe(1);
    expect(parsed.pricing.status).toBe('known');
  });

  it('requires Runtime-proved savings instead of recomputing or inventing it', () => {
    expect(() => parseCostProjection({
      ...fixture,
      rows: [{ ...fixture.rows[0], saved_cost_usd: 0 }, fixture.rows[1]],
    })).toThrow('cost_projection_invalid');
  });

  it('accepts the contract availability state and rejects impossible numeric savings', () => {
    const unavailable = parseCostProjection({
      ...fixture,
      baseline: {
        ...fixture.baseline,
        identity_status: 'unavailable',
        versions: [],
        methods: [],
      },
    });
    expect(unavailable.baseline.identity_status).toBe('unavailable');
    expect(() => parseCostProjection({
      ...fixture,
      rows: [{ ...fixture.rows[0], baseline_tokens: 200 } , fixture.rows[1]],
    })).toThrow('cost_projection_invalid');
  });

  it('rejects unknown properties and non-digest project selectors', () => {
    expect(() => parseCostProjection({ ...fixture, unexpected: true })).toThrow('cost_projection_invalid');
    expect(() => parseCostProjection({
      ...fixture,
      query: { project_id: '/private/project' },
    })).toThrow('cost_projection_invalid');
    expect(() => parseCostProjection({
      ...fixture,
      rows: [{ ...fixture.rows[0], provider: 'não' }, fixture.rows[1]],
    })).toThrow('cost_projection_invalid');
  });

  it('never presents actual cost when Runtime pricing is unavailable', () => {
    expect(() => parseCostProjection({
      ...fixture,
      pricing: {
        status: 'unavailable', identity: null, version: null, versions: [], sources: [],
      },
    })).toThrow('cost_projection_pricing_invalid');
  });

  it('rejects preview, paths, and sensitive fields', () => {
    expect(() => parseCostProjection({ ...fixture, preview: true })).toThrow('cost_projection_sensitive_field');
    expect(() => parseCostProjection({
      ...fixture,
      rows: [{ ...fixture.rows[0], path: '/private/project' }, fixture.rows[1]],
    })).toThrow('cost_projection_sensitive_field');
  });

  it('exports bounded JSON and CSV without raw prompts or paths', () => {
    const json = exportCostProjection(fixture, 'json');
    const csv = exportCostProjection(fixture, 'csv');
    expect(json).toContain('simplicio.desktop-cost-projection/v1');
    expect(csv.split('\n')[0]).toContain('actual_cost_usd');
    expect(csv).toContain('provider-reported');
    expect(csv).not.toContain('private');
  });
});
