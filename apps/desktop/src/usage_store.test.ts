import { describe, expect, it } from "vitest";
import { createUsageChangefeedState } from "./usage_changefeed";
import {
  createDesktopUsageStore,
  createUsageChangefeedSupervisor,
  MAX_IDLE_FINALIZATION_HISTORY,
  type UsageChangefeedFetcher,
} from "./usage_store";
import { IDLE_SESSION_TIMEOUT_MS, type IdleSessionFinalization } from "./session_idle";

describe("Desktop usage store", () => {
  it("publishes immutable changefeed state and preserves it when offline", () => {
    const store = createDesktopUsageStore();
    const seen: string[] = [];
    const unsubscribe = store.subscribe((state) => seen.push(state.changefeed.connection));

    store.replaceChangefeed({ ...createUsageChangefeedState(), connection: "stale" });
    store.markOffline("test_offline");
    unsubscribe();

    expect(store.getState().changefeed.connection).toBe("offline");
    expect(store.getState().changefeed.reason_code).toBe("test_offline");
    expect(seen).toEqual(["stale", "offline"]);
  });

  it("bounds queued events and exposes queue pressure instead of dropping silently", () => {
    const fetcher: UsageChangefeedFetcher = async () => createUsageChangefeedState();
    const supervisor = createUsageChangefeedSupervisor(fetcher, { maxQueue: 1 });

    expect(supervisor.enqueue({})).toBe(true);
    expect(supervisor.enqueue({})).toBe(false);
    expect(supervisor.getState().reason_code).toBe("usage_changefeed_queue_full");
  });

  it("stops an in-flight poll and keeps the final state offline", async () => {
    let resolveFetch: ((state: ReturnType<typeof createUsageChangefeedState>) => void) | undefined;
    const fetcher: UsageChangefeedFetcher = () => new Promise((resolve) => {
      resolveFetch = resolve;
    });
    const supervisor = createUsageChangefeedSupervisor(fetcher, { pollIntervalMs: 10 });
    supervisor.start();
    await new Promise((resolve) => setTimeout(resolve, 5));

    const stopping = supervisor.stop();
    resolveFetch?.(createUsageChangefeedState());
    await stopping;

    expect(supervisor.getState().connection).toBe("offline");
    expect(supervisor.getState().reason_code).toBe("usage_changefeed_stopped");
  });

  it("records idle finalizations once, replays the same id, and bounds history", () => {
    const store = createDesktopUsageStore();
    const receipt = (id: string, now: number): IdleSessionFinalization => ({
      schema: "simplicio.session-idle-finalization/v1",
      status: "logical_closed",
      finalization_id: id,
      profile_id: "default",
      workspace_id: "/workspace",
      now_millis: now,
      idle_ms: IDLE_SESSION_TIMEOUT_MS,
      closed_sessions: [{ session_id: "s1", status: "idle", updated_at: now }],
      usage: {
        status: "pending_provider_refresh",
        metrics: ["input_tokens", "output_tokens", "reasoning_tokens", "cache_read_tokens", "cache_write_tokens"],
      },
      provider_processes_terminated: false,
      redacted: true,
    });
    store.setIdleFinalization(receipt("sha256:one", 1));
    store.setIdleFinalization(receipt("sha256:one", 2));
    store.setIdleFinalization(receipt("sha256:two", 3));
    expect(store.getState().idleFinalization?.finalization_id).toBe("sha256:two");
    expect(store.getState().idleHistory.map((item) => item.finalization_id)).toEqual(["sha256:two", "sha256:one"]);
    for (let index = 0; index < MAX_IDLE_FINALIZATION_HISTORY + 3; index += 1) {
      store.setIdleFinalization(receipt(`sha256:${index}`, 10 + index));
    }
    expect(store.getState().idleHistory).toHaveLength(MAX_IDLE_FINALIZATION_HISTORY);
  });
});
