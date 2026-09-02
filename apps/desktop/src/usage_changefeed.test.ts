import { describe, expect, it } from "vitest";
import {
  applyUsageChangefeedEvent,
  createUsageChangefeedState,
  markUsageChangefeedOffline,
} from "./usage_changefeed";
import type { UnifiedUsageProjection } from "./unified_usage";

const projection: UnifiedUsageProjection = {
  schema: "simplicio.desktop-unified-usage/v1",
  generated_at_epoch: 1700000100,
  query: {},
  rows: [{
    provider: "openai", model: "gpt-5", host: "codex",
    project_id: null, session_id: "session-1", execution: "remote",
    input_tokens: 10, cache_read_tokens: 2, cache_write_tokens: 1,
    output_tokens: 4, reasoning_tokens: 1, total_tokens: 15, cost_usd: null,
    provenance: "unavailable", event_count: 1,
  }],
  totals: {
    event_count: 1, input_tokens: 10, cache_read_tokens: 2, cache_write_tokens: 1,
    output_tokens: 4, reasoning_tokens: 1, total_tokens: 15, cost_usd: null,
  },
  metadata: {
    source: "runtime", generated_by: "runtime_usage_ledger", generated_at_epoch: 1700000100,
    report_digest: "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    pricing_version: null, pricing_sources: [],
    coverage: { status: "no_data", missing_usage_events: 0, unpriced_events: 0, providers: [], reason: null },
    redacted: true,
  },
};

function event(sequence: number, revision = sequence, eventId = `event-${sequence}`) {
  return {
    schema: "simplicio.desktop-usage-changefeed/v1",
    event_id: eventId, sequence, revision, kind: sequence === 1 ? "snapshot" : "delta",
    generated_at_epoch: 1700000100 + sequence, projection,
  };
}

describe("Runtime usage changefeed", () => {
  it("applies a snapshot and an in-order delta while advancing the cursor", () => {
    let state = applyUsageChangefeedEvent(createUsageChangefeedState(), event(1));
    state = applyUsageChangefeedEvent(state, event(2));
    expect(state.connection).toBe("live");
    expect(state.cursor).toEqual({ sequence: 2, revision: 2, event_ids: ["event-1", "event-2"] });
    expect(state.projection?.totals.total_tokens).toBe(15);
  });

  it("deduplicates replayed event IDs without changing the projection", () => {
    const first = applyUsageChangefeedEvent(createUsageChangefeedState(), event(1));
    const replay = applyUsageChangefeedEvent(first, event(1, 1, "event-1"));
    expect(replay.reason_code).toBe("usage_changefeed_duplicate_ignored");
    expect(replay.cursor.sequence).toBe(1);
  });

  it("preserves the last projection and asks for replay when a sequence gap appears", () => {
    const first = applyUsageChangefeedEvent(createUsageChangefeedState(), event(1));
    const gap = applyUsageChangefeedEvent(first, event(3));
    expect(gap.connection).toBe("reconnecting");
    expect(gap.projection).toBe(first.projection);
    expect(gap.cursor.sequence).toBe(1);
  });

  it("keeps last known data when transport goes offline", () => {
    const first = applyUsageChangefeedEvent(createUsageChangefeedState(), event(1));
    const offline = markUsageChangefeedOffline(first);
    expect(offline.connection).toBe("offline");
    expect(offline.projection).toBe(first.projection);
  });

  it("rejects untrusted projection data before it reaches the renderer state", () => {
    expect(() => applyUsageChangefeedEvent(createUsageChangefeedState(), {
      ...event(1), projection: { ...projection, metadata: { ...projection.metadata, redacted: false } },
    })).toThrow("usage_projection_untrusted_source");
  });
});
