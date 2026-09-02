import {
  applyUsageChangefeedEvent,
  createUsageChangefeedState,
  markUsageChangefeedOffline,
  type UsageChangefeedState,
} from "./usage_changefeed";

export interface DesktopUsageState {
  changefeed: UsageChangefeedState;
}

export type DesktopUsageListener = (state: DesktopUsageState) => void;

export interface DesktopUsageStore {
  getState(): DesktopUsageState;
  subscribe(listener: DesktopUsageListener): () => void;
  replaceChangefeed(state: UsageChangefeedState): void;
  applyEvent(value: unknown): void;
  markOffline(reasonCode?: string): void;
}

export function createDesktopUsageStore(
  initial: UsageChangefeedState = createUsageChangefeedState(),
): DesktopUsageStore {
  let state: DesktopUsageState = { changefeed: initial };
  const listeners = new Set<DesktopUsageListener>();

  function notify() {
    for (const listener of listeners) listener(state);
  }

  return {
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    replaceChangefeed(changefeed) {
      state = { changefeed };
      notify();
    },
    applyEvent(value) {
      state = { changefeed: applyUsageChangefeedEvent(state.changefeed, value) };
      notify();
    },
    markOffline(reasonCode) {
      state = { changefeed: markUsageChangefeedOffline(state.changefeed, reasonCode) };
      notify();
    },
  };
}

export type UsageChangefeedFetcher = (
  cursor: UsageChangefeedState,
) => Promise<UsageChangefeedState>;

export interface UsageChangefeedSupervisorOptions {
  initialState?: UsageChangefeedState;
  pollIntervalMs?: number;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  maxQueue?: number;
  onState?: (state: UsageChangefeedState) => void;
}

export interface UsageChangefeedSupervisor {
  start(): void;
  stop(): Promise<void>;
  enqueue(value: unknown): boolean;
  getState(): UsageChangefeedState;
  subscribe(listener: (state: UsageChangefeedState) => void): () => void;
}

const DEFAULT_POLL_INTERVAL_MS = 5_000;
const DEFAULT_INITIAL_BACKOFF_MS = 250;
const DEFAULT_MAX_BACKOFF_MS = 8_000;
const DEFAULT_MAX_QUEUE = 64;

function boundedNumber(value: number | undefined, fallback: number): number {
  return Number.isFinite(value) && value !== undefined && value >= 0 ? value : fallback;
}

export function createUsageChangefeedSupervisor(
  fetcher: UsageChangefeedFetcher,
  options: UsageChangefeedSupervisorOptions = {},
): UsageChangefeedSupervisor {
  let state = options.initialState ?? createUsageChangefeedState();
  let running = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let inFlight: Promise<void> | null = null;
  let epoch = 0;
  let failures = 0;
  const pending: unknown[] = [];
  const listeners = new Set<(next: UsageChangefeedState) => void>();
  const pollIntervalMs = boundedNumber(options.pollIntervalMs, DEFAULT_POLL_INTERVAL_MS);
  const initialBackoffMs = boundedNumber(options.initialBackoffMs, DEFAULT_INITIAL_BACKOFF_MS);
  const maxBackoffMs = Math.max(
    initialBackoffMs,
    boundedNumber(options.maxBackoffMs, DEFAULT_MAX_BACKOFF_MS),
  );
  const maxQueue = Math.max(1, Math.floor(boundedNumber(options.maxQueue, DEFAULT_MAX_QUEUE)));

  function emit() {
    options.onState?.(state);
    for (const listener of listeners) listener(state);
  }

  function schedule(delayMs: number) {
    if (!running || timer !== null) return;
    timer = setTimeout(() => {
      timer = null;
      void drain();
    }, Math.max(0, delayMs));
  }

  function backoffDelay() {
    return Math.min(maxBackoffMs, initialBackoffMs * (2 ** Math.min(failures - 1, 10)));
  }

  async function drain(): Promise<void> {
    if (!running || inFlight) return;

    if (pending.length > 0) {
      const value = pending.shift();
      try {
        state = applyUsageChangefeedEvent(state, value);
        failures = 0;
      } catch (cause) {
        state = {
          ...state,
          connection: "reconnecting",
          reason_code: cause instanceof Error && cause.message === "usage_changefeed_invalid"
            ? cause.message
            : "usage_changefeed_event_rejected",
        };
        failures += 1;
      }
      emit();
      schedule(failures > 0 ? backoffDelay() : pollIntervalMs);
      return;
    }

    const requestEpoch = epoch;
    const request = fetcher(state);
    inFlight = request
      .then((next) => {
        if (!running || requestEpoch !== epoch) return;
        state = next;
        failures = 0;
        emit();
      })
      .catch(() => {
        if (!running || requestEpoch !== epoch) return;
        failures += 1;
        state = {
          ...state,
          connection: "reconnecting",
          reason_code: "usage_changefeed_transport_error",
        };
        emit();
      })
      .finally(() => {
        inFlight = null;
        if (running && requestEpoch === epoch) {
          schedule(failures > 0 ? backoffDelay() : pollIntervalMs);
        }
      });
    await inFlight;
  }

  return {
    start() {
      if (running) return;
      running = true;
      schedule(0);
    },
    async stop() {
      if (!running && !inFlight) return;
      running = false;
      epoch += 1;
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
      if (inFlight) await inFlight;
      state = markUsageChangefeedOffline(state, "usage_changefeed_stopped");
      emit();
    },
    enqueue(value) {
      if (pending.length >= maxQueue) {
        state = { ...state, connection: "reconnecting", reason_code: "usage_changefeed_queue_full" };
        emit();
        return false;
      }
      pending.push(value);
      if (running) schedule(0);
      return true;
    },
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
