import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { invokeMock } = vi.hoisted(() => ({ invokeMock: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

function deferred() {
  let resolve!: (value: unknown) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.resetModules();
  vi.useFakeTimers();
  vi.stubGlobal("window", { __TAURI_INTERNALS__: {} });
  invokeMock.mockReset();
});
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("read-only snapshot boundary", () => {
  it("ends the loading wait without starting another native query while the first is pending", async () => {
    const native = deferred();
    invokeMock.mockReturnValue(native.promise);
    const bridge = await import("./bridge");
    const first = vi.fn();
    const second = vi.fn();
    void bridge.loadDesktopSnapshot().then(first, first);
    void bridge.refreshDesktopSnapshot().then(second, second);
    await vi.advanceTimersByTimeAsync(30_001);
    expect(first).toHaveBeenCalledWith(expect.objectContaining({ message: "desktop_snapshot_timeout" }));
    expect(second).toHaveBeenCalledWith(expect.objectContaining({ message: "desktop_snapshot_timeout" }));
    expect(invokeMock).toHaveBeenCalledTimes(1);
    await expect(bridge.refreshDesktopSnapshot()).rejects.toThrow("desktop_snapshot_timeout");
    expect(invokeMock).toHaveBeenCalledTimes(1);
    native.resolve({ marker: "late" });
    await vi.advanceTimersByTimeAsync(0);
    expect(first).toHaveBeenCalledTimes(1);
    expect(second).toHaveBeenCalledTimes(1);
    invokeMock.mockResolvedValueOnce({ marker: "fresh" });
    await expect(bridge.refreshDesktopSnapshot()).resolves.toEqual({ marker: "fresh" });
    expect(invokeMock).toHaveBeenCalledTimes(2);
  });

  it("releases the read slot after rejection and does not cache completed snapshots", async () => {
    invokeMock.mockRejectedValueOnce(new Error("snapshot_unavailable"));
    const bridge = await import("./bridge");
    await expect(bridge.loadDesktopSnapshot()).rejects.toThrow("snapshot_unavailable");
    invokeMock.mockResolvedValueOnce({ marker: "one" }).mockResolvedValueOnce({ marker: "two" });
    await expect(bridge.refreshDesktopSnapshot()).resolves.toEqual({ marker: "one" });
    await expect(bridge.refreshDesktopSnapshot()).resolves.toEqual({ marker: "two" });
    expect(vi.getTimerCount()).toBe(0);
  });

  it("does not time out or replay login, logout or installation", async () => {
    const native = deferred();
    invokeMock.mockReturnValue(native.promise);
    const bridge = await import("./bridge");
    const outcome = vi.fn();
    void bridge.installDesktopRuntime().then(outcome, outcome);
    void bridge.beginDesktopLogin().then(outcome, outcome);
    void bridge.logoutDesktop().then(outcome, outcome);
    void bridge.applyDesktopHostPlugins(`sha256:${"a".repeat(64)}`).then(outcome, outcome);
    void bridge.reconcileDesktopHostPlugins(`sha256:${"b".repeat(64)}`).then(outcome, outcome);
    await vi.advanceTimersByTimeAsync(120_000);
    expect(outcome).not.toHaveBeenCalled();
    expect(invokeMock.mock.calls.map(([command]) => command)).toEqual(["desktop_install_runtime", "desktop_login", "desktop_logout", "desktop_apply_host_plugins", "desktop_reconcile_host_plugins"]);
    native.resolve({ marker: "completed" });
    await vi.advanceTimersByTimeAsync(0);
    expect(outcome).toHaveBeenCalledTimes(5);
  });
});
