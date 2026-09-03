import { describe, expect, it } from 'vitest';
import { parseUnifiedUsageProjection, unifiedUsageState } from './unified_usage';

const digest = (character: string) => `sha256:${character.repeat(64)}`;

describe('Runtime desktop unified usage v1 states', () => {
  it('accepts the exact bounded no-data payload without inventing consumption', () => {
    const projection = parseUnifiedUsageProjection({
      schema: 'simplicio.desktop-unified-usage/v1',
      generated_at_epoch: 0,
      query: {},
      rows: [],
      totals: {
        event_count: 0,
        input_tokens: 0,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        reported_output_tokens: 0,
        output_tokens: 0,
        reasoning_tokens: 0,
        total_tokens: 0,
        cost_usd: 0,
      },
      metadata: {
        source: 'runtime',
        generated_by: 'runtime_usage_ledger',
        generated_at_epoch: 0,
        report_digest: digest('a'),
        revision: digest('b'),
        pricing_version: null,
        pricing_sources: [],
        coverage: {
          status: 'no_data',
          missing_usage_events: 0,
          unpriced_events: 0,
          providers: [],
          reason: 'no_matching_usage',
        },
        redacted: true,
      },
    });

    expect(projection.metadata.coverage.status).toBe('no_data');
    expect(projection.rows).toEqual([]);
    expect(unifiedUsageState(projection)).toEqual({
      showMetrics: false,
      message: 'Nenhum evento corresponde aos filtros; consumo não foi presumido como zero.',
    });
  });

  it('preserves partial completeness and unavailable provenance from Runtime', () => {
    const projection = parseUnifiedUsageProjection({
      schema: 'simplicio.desktop-unified-usage/v1',
      generated_at_epoch: 1700000100,
      query: { provider: 'openai' },
      rows: [{
        provider: 'openai',
        model: 'gpt-5',
        host: 'codex',
        project_id: 'project-redacted',
        session_id: 'session-redacted',
        execution: 'remote',
        input_tokens: 100,
        cache_read_tokens: 20,
        cache_write_tokens: 0,
        reported_output_tokens: 50,
        output_tokens: 40,
        reasoning_tokens: 10,
        total_tokens: 150,
        cost_usd: null,
        provenance: 'provider-reported',
        reasoning_semantics: 'included_in_output',
        reasoning_semantics_provenance: 'provider-reported',
        reasoning_semantics_reason: null,
        event_count: 1,
        source_completeness: 'partial',
        incomplete_events: 1,
        missing_usage_events: 1,
        unpriced_events: 1,
        metric_provenance: {
          input_tokens: ['provider-reported'],
          paid_remote_tokens: ['unavailable'],
        },
        missing_metrics: { paid_remote_tokens: 1 },
      }],
      totals: {
        event_count: 1,
        input_tokens: 100,
        cache_read_tokens: 20,
        cache_write_tokens: 0,
        reported_output_tokens: 50,
        output_tokens: 40,
        reasoning_tokens: 10,
        total_tokens: 150,
        cost_usd: null,
      },
      metadata: {
        source: 'runtime',
        generated_by: 'runtime_usage_ledger',
        generated_at_epoch: 1700000100,
        report_digest: digest('c'),
        revision: digest('d'),
        pricing_version: null,
        pricing_sources: [],
        coverage: {
          status: 'partial',
          missing_usage_events: 1,
          unpriced_events: 1,
          providers: ['openai'],
          reason: 'usage_metrics_missing',
        },
        redacted: true,
      },
    });

    expect(projection.metadata.coverage.status).toBe('partial');
    expect(projection.rows[0].source_completeness).toBe('partial');
    expect(projection.rows[0].reasoning_semantics).toBe('included_in_output');
    expect(projection.rows[0].metric_provenance.paid_remote_tokens).toEqual(['unavailable']);
    expect(projection.rows[0].missing_metrics).toEqual({ paid_remote_tokens: 1 });
    expect(unifiedUsageState(projection).showMetrics).toBe(true);
    expect(unifiedUsageState(projection).message).toContain('Cobertura parcial');
  });

  it('rejects sensitive renderer payloads before any state can be rendered', () => {
    const payload = {
      schema: 'simplicio.desktop-unified-usage/v1',
      prompt: 'secret',
    };
    expect(() => parseUnifiedUsageProjection(payload)).toThrow('usage_projection_sensitive_field');
  });
});
