import { parseUnifiedUsageProjection, type UnifiedUsageProjection } from "./unified_usage";
import { parseCostProjection, type CostProjection } from "./cost_projection";

export const USAGE_CHANGEFEED_SCHEMA = "simplicio.desktop-usage-changefeed/v1";
export const MAX_CHANGEFEED_EVENT_IDS = 128;

export type UsageChangefeedConnection = "live" | "reconnecting" | "stale" | "offline";
export type UsageChangefeedKind = "snapshot" | "delta";

export interface UsageChangefeedEvent {
  schema: typeof USAGE_CHANGEFEED_SCHEMA;
  event_id: string;
  sequence: number;
  revision: number;
  kind: UsageChangefeedKind;
  generated_at_epoch: number;
  projection: unknown;
  cost_projection?: unknown;
}

export interface UsageChangefeedCursor {
  sequence: number;
  revision: number;
  event_ids: string[];
}

export interface UsageChangefeedState {
  connection: UsageChangefeedConnection;
  cursor: UsageChangefeedCursor;
  projection: UnifiedUsageProjection | null;
  cost_projection: CostProjection | null;
  last_event_at_epoch: number | null;
  reason_code: string;
}

const KINDS: UsageChangefeedKind[] = ["snapshot", "delta"];

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("usage_changefeed_invalid");
  }
  return value as Record<string, unknown>;
}

function text(value: unknown): string {
  if (typeof value !== "string" || value.length === 0 || value.length > 256
    || /[\\/\u0000-\u001f\u007f]/.test(value)) {
    throw new Error("usage_changefeed_invalid");
  }
  return value;
}

function integer(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new Error("usage_changefeed_invalid");
  }
  return value;
}

function parseEvent(value: unknown): UsageChangefeedEvent {
  const raw = record(value);
  const kind = text(raw.kind);
  if (!KINDS.includes(kind as UsageChangefeedKind)) throw new Error("usage_changefeed_invalid");
  return {
    schema: raw.schema === USAGE_CHANGEFEED_SCHEMA ? USAGE_CHANGEFEED_SCHEMA : (() => {
      throw new Error("usage_changefeed_invalid");
    })(),
    event_id: text(raw.event_id),
    sequence: integer(raw.sequence),
    revision: integer(raw.revision),
    kind: kind as UsageChangefeedKind,
    generated_at_epoch: integer(raw.generated_at_epoch),
    projection: raw.projection,
    ...(raw.cost_projection === undefined ? {} : { cost_projection: raw.cost_projection }),
  };
}

export function createUsageChangefeedState(): UsageChangefeedState {
  return {
    connection: "offline",
    cursor: { sequence: 0, revision: 0, event_ids: [] },
    projection: null,
    cost_projection: null,
    last_event_at_epoch: null,
    reason_code: "usage_changefeed_unavailable",
  };
}

function remember(cursor: UsageChangefeedCursor, eventId: string): UsageChangefeedCursor {
  return {
    sequence: cursor.sequence,
    revision: cursor.revision,
    event_ids: [...cursor.event_ids, eventId].slice(-MAX_CHANGEFEED_EVENT_IDS),
  };
}

export function applyUsageChangefeedEvent(
  state: UsageChangefeedState,
  value: unknown,
): UsageChangefeedState {
  const event = parseEvent(value);
  if (state.cursor.event_ids.includes(event.event_id)) {
    return { ...state, connection: "live", reason_code: "usage_changefeed_duplicate_ignored" };
  }
  if (event.sequence <= state.cursor.sequence || event.revision <= state.cursor.revision) {
    return { ...state, connection: "stale", reason_code: "usage_changefeed_stale_ignored" };
  }
  if (state.cursor.sequence > 0 && event.sequence !== state.cursor.sequence + 1) {
    return { ...state, connection: "reconnecting", reason_code: "usage_changefeed_gap" };
  }

  const projection = parseUnifiedUsageProjection(event.projection);
  const cost_projection = event.cost_projection === undefined
    ? state.cost_projection
    : parseCostProjection(event.cost_projection);
  const cursor = remember({ ...state.cursor, sequence: event.sequence, revision: event.revision }, event.event_id);
  return {
    connection: "live",
    cursor,
    projection,
    cost_projection,
    last_event_at_epoch: event.generated_at_epoch,
    reason_code: event.kind === "delta" ? "usage_changefeed_delta_applied" : "usage_changefeed_snapshot_applied",
  };
}

export function markUsageChangefeedOffline(
  state: UsageChangefeedState,
  reasonCode = "usage_changefeed_offline",
): UsageChangefeedState {
  return { ...state, connection: "offline", reason_code: reasonCode };
}
