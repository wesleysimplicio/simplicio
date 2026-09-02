import { describe, expect, it } from "vitest";
import { createUsageChangefeedState } from "./usage_changefeed";
import {
  createDesktopUsageStore,
  createUsageChangefeedSupervisor,
  type UsageChangefeedFetcher,
} from "./usage_store";

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
});
