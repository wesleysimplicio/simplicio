import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { invokeMock } = vi.hoisted(() => ({ invokeMock: vi.fn() }));

vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

const NO_DATA = {
  schema: "simplicio.desktop-unified-usage/v1",
  generated_at_epoch: 0,
  query: { provider: "openai" },
  rows: [],
  totals: {
    input_tokens: 0,
    cache_read_tokens: 0,
    cache_write_tokens: 0,
    reported_output_tokens: 0,
    output_tokens: 0,
    reasoning_tokens: 0,
    total_tokens: 0,
    cost_usd: 0,
    event_count: 0,
  },
  metadata: {
    generated_by: "runtime_usage_ledger",
    source: "runtime",
    generated_at_epoch: 0,
    report_digest: "sha256:a78554c978a2fb65c8aec801d42b93539025b27ec9715aa54d9f8be45a2142f8",
    revision: "sha256:5eed768be80b989f7a0d53033265b00f398bd7e88ba111f2c301936764118f37",
    pricing_version: null,
    pricing_sources: [],
    coverage: {
      status: "no_data",
      missing_usage_events: 0,
      unpriced_events: 0,
      providers: [],
      reason: "no_matching_usage",
    },
    redacted: true,
  },
};

beforeEach(() => {
  vi.resetModules();
  vi.stubGlobal("window", {
    __TAURI_INTERNALS__: {},
    setTimeout: globalThis.setTimeout,
    clearTimeout: globalThis.clearTimeout,
  });
  invokeMock.mockReset();
});

afterEach(() => vi.unstubAllGlobals());

describe("desktop unified usage bridge", () => {
  it("forwards only the query and native repo selector to the real Tauri command", async () => {
    invokeMock.mockResolvedValue(NO_DATA);
    const bridge = await import("./bridge");

    const result = await bridge.loadDesktopUnifiedUsage({ provider: "openai" }, "/tmp/project");

    expect(invokeMock).toHaveBeenCalledOnce();
    expect(invokeMock).toHaveBeenCalledWith("desktop_unified_usage", {
      query: { provider: "openai" },
      repoPath: "/tmp/project",
    });
    expect(result.metadata.source).toBe("runtime");
    expect(result.rows).toEqual([]);
  });

  it("does not offer a browser preview when no packaged Runtime boundary exists", async () => {
    vi.stubGlobal("window", {});
    const bridge = await import("./bridge");

    await expect(bridge.loadDesktopUnifiedUsage()).rejects.toThrow("preview_no_runtime");
    expect(invokeMock).not.toHaveBeenCalled();
  });
});
