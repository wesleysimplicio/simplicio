import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { emptyWorkbench, isSettingsView, isView, MAX_PROJECTS, moveHistory, navigate, parseLocalProject, parseWorkbench, runtimeSummary, searchMatches, type NavigationEntry, type NavigationState } from "./workbench";
import type { ContextReport } from "./context_report";

function project(index = 0) {
  return { id: "project-" + index.toString(16).padStart(64, "0"), name: "Meu projeto " + index, path: "/projects/local-" + index };
}

function route(view: NavigationEntry["view"], projectId: string | null = null, tokenRepo = ""): NavigationEntry {
  return { view, projectId, tokenRepo };
}

describe("local workbench state", () => {
  it("recovers safely from malformed, unknown and oversized storage", () => {
    for (const raw of [null, "", "broken json", "[]", '{"schema":"unknown"}', "x".repeat(180001)]) {
      expect(parseWorkbench(raw)).toEqual(emptyWorkbench());
    }
  });

  it("retains only bounded local bookmarks and visual preferences", () => {
    const state = parseWorkbench(JSON.stringify({ ...emptyWorkbench(), projects: [project(), project(), { path: "../bad" }, project(1)],
      selectedProjectId: project(1).id, preferences: { density: "compact", showProjectPaths: true, rememberProject: true, dangerousMode: true } }));
    expect(state.projects).toEqual([project(), project(1)]);
    expect(state.selectedProjectId).toBe(project(1).id);
    expect(state.preferences).toEqual({ ...emptyWorkbench().preferences, density: "compact", showProjectPaths: true, rememberProject: true });
    expect(JSON.stringify(state)).not.toContain("dangerousMode");
    expect(parseWorkbench(JSON.stringify({ ...state, projects: Array.from({ length: 100 }, (_, index) => project(index)) })).projects).toHaveLength(MAX_PROJECTS);
  });

  it("does not restore removed projects or a disabled remember preference", () => {
    for (const preferences of [{ rememberProject: false }, { rememberProject: true }]) {
      const state = parseWorkbench(JSON.stringify({ ...emptyWorkbench(), projects: [project()], selectedProjectId: project(9).id, preferences }));
      expect(state.selectedProjectId).toBeNull();
    }
    expect(parseWorkbench(JSON.stringify({ ...emptyWorkbench(), projects: [project()], selectedProjectId: project().id,
      preferences: { rememberProject: false } })).selectedProjectId).toBeNull();
  });

  it("keeps the launch preference bounded and restores only a workbench view", () => {
    const state = parseWorkbench(JSON.stringify({ ...emptyWorkbench(), preferences: {
      ...emptyWorkbench().preferences, launchBehavior: "last_view", lastView: "activity",
    } }));
    expect(state.preferences.launchBehavior).toBe("last_view");
    expect(state.preferences.lastView).toBe("activity");
    const unsafe = parseWorkbench(JSON.stringify({ ...emptyWorkbench(), preferences: {
      ...emptyWorkbench().preferences, launchBehavior: "last_view", lastView: "settings",
    } }));
    expect(unsafe.preferences.lastView).toBe("home");
  });

  it("rejects untrusted project identifiers, remote paths and control characters", () => {
    for (const path of ["../project", "https://example.com", "//server/share", "\\\\server\\share", "/local\nsecret"]) {
      expect(() => parseLocalProject({ ...project(), path })).toThrow();
    }
    expect(() => parseLocalProject({ ...project(), id: "__proto__" })).toThrow();
    expect(() => parseLocalProject({ ...project(), name: "" })).toThrow();
    expect(parseLocalProject({ ...project(), path: "C:\\projects\\app" }).path).toBe("C:\\projects\\app");
    expect(parseLocalProject({ ...project(), credential: "SECRET" })).not.toHaveProperty("credential");
  });
});

describe("workbench navigation and evidence", () => {
  it("restores the project and token scope through A, tokens A, B, tokens B and back/forward", () => {
    const a = project(1);
    const b = project(2);
    const expected = [route("home"), route("project", a.id), route("tokens", a.id, a.path), route("project", b.id), route("tokens", b.id, b.path)];
    let history: NavigationState = { entries: [expected[0]], index: 0 };
    for (const entry of expected.slice(1)) history = navigate(history, entry);
    expect(history.entries).toEqual(expected);
    expect(history.entries[history.index]).toEqual(expected.at(-1));

    for (let index = expected.length - 2; index >= 0; index--) {
      history = moveHistory(history, -1);
      expect(history.entries[history.index]).toEqual(expected[index]);
    }
    expect(moveHistory(history, -1).index).toBe(0);
    for (let index = 1; index < expected.length; index++) {
      history = moveHistory(history, 1);
      expect(history.entries[history.index]).toEqual(expected[index]);
    }
    expect(moveHistory(history, 1).index).toBe(expected.length - 1);
  });

  it("does not deduplicate a different project or token scope on the same view", () => {
    const a = project(1);
    const b = project(2);
    let history: NavigationState = { entries: [route("project", a.id)], index: 0 };
    history = navigate(history, route("project", b.id));
    expect(history.entries).toEqual([route("project", a.id), route("project", b.id)]);
    history = navigate(history, route("tokens", b.id, b.path));
    history = navigate(history, route("tokens", b.id, a.path));
    expect(history.entries).toHaveLength(4);
    expect(history.entries[history.index]).toEqual(route("tokens", b.id, a.path));
  });

  it("preserves the complete current route and forward branch when deduplicating", () => {
    const a = project(1);
    const current = route("tokens", a.id, a.path);
    const next = route("project", project(2).id);
    const history: NavigationState = { entries: [route("home"), current, next], index: 1 };
    const unchanged = navigate(history, { ...current });
    expect(unchanged).toBe(history);
    expect(unchanged.entries[unchanged.index]).toEqual(current);
    expect(unchanged.entries).toEqual([route("home"), current, next]);
    expect(moveHistory(unchanged, 1).entries[2]).toEqual(next);
  });

  it("discards a forward branch only after distinct navigation", () => {
    const a = project(1);
    let history: NavigationState = { entries: [route("home")], index: 0 };
    history = navigate(history, route("tokens", a.id, a.path));
    history = navigate(history, route("providers", a.id));
    history = moveHistory(history, -1);
    history = navigate(history, route("settings", a.id));
    expect(history.entries).toEqual([route("home"), route("tokens", a.id, a.path), route("settings", a.id)]);
    expect(moveHistory(history, 1).index).toBe(2);
  });

  it("retains only the latest 50 route snapshots and clamps history movement", () => {
    let history: NavigationState = { entries: [route("home")], index: 0 };
    for (let index = 0; index < 100; index++) {
      const selected = project(index);
      history = navigate(history, route("tokens", selected.id, selected.path));
    }
    expect(history.entries).toHaveLength(50);
    expect(history.index).toBe(49);
    expect(history.entries[0]).toEqual(route("tokens", project(50).id, project(50).path));
    expect(history.entries[49]).toEqual(route("tokens", project(99).id, project(99).path));
    expect(moveHistory(history, 1).index).toBe(49);
    expect(moveHistory({ entries: [route("home")], index: 0 }, -1).index).toBe(0);
  });

  it("captures input routes without mutating prior state or retaining the caller's object", () => {
    const a = project(1);
    const destination = route("tokens", a.id, a.path);
    const initial: NavigationState = { entries: [route("home")], index: 0 };
    const history = navigate(initial, destination);
    destination.projectId = project(2).id;
    destination.tokenRepo = project(2).path;
    expect(initial).toEqual({ entries: [route("home")], index: 0 });
    expect(history.entries[history.index]).toEqual(route("tokens", a.id, a.path));
    expect(history.entries[history.index]).not.toBe(destination);
  });

  it("searches accent-insensitively without accepting inherited route keys", () => {
    expect(searchMatches("Integrações MCP", "integracoes")).toBe(true);
    expect(searchMatches("Agentes e IDEs", "  IDE  ")).toBe(true);
    expect(searchMatches("Conta", "runtime")).toBe(false);
    expect(isView("toString")).toBe(false);
    expect(isView("__proto__")).toBe(false);
    expect(isView("project")).toBe(true);
    expect(isSettingsView("providers")).toBe(true);
    expect(isSettingsView("home")).toBe(false);
  });

  it("prefers a verified project context report for measured savings", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    snapshot.savings.proofKind = "mixed";
    const contextReport: ContextReport = {
      schema: "simplicio.desktop-context-report/v1",
      source: "runtime",
      scope: "project_history",
      eventCount: 12,
      ledgerEventCount: 12,
      llmSpendEventCount: 0,
      savedTokens: 350,
      baselineTokens: 1000,
      actualTokens: 650,
      netTokens: 350,
      baselineKind: "measured",
      confidence: "medium",
      heuristicEventCount: 0,
      unlabeledEstimateCount: 0,
      proof: { measured: 12, estimated: 0, replayed: 0, benchmark: 0, unavailable: 0 },
      reportHash: "sha256:" + "a".repeat(64),
    };
    expect(runtimeSummary(snapshot, contextReport).measuredSavings).toBe(350);
    contextReport.netTokens = -25;
    expect(runtimeSummary(snapshot, contextReport).measuredSavings).toBeNull();
  });

  it("never labels an offline Runtime online or counts an unverified MCP as live", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.runtime.state = "offline";
    snapshot.providers.forEach((provider) => { provider.state = "connected"; provider.handshakeState = "unverified"; });
    expect(runtimeSummary(snapshot)).toMatchObject({ label: "Runtime offline", healthy: false, connected: 0 });
    snapshot.savings.proofKind = "mixed";
    expect(runtimeSummary(snapshot).measuredSavings).toBeNull();
    snapshot.savings.proofKind = "measured"; snapshot.savings.ledgerStatus = "valid";
    expect(runtimeSummary(snapshot).measuredSavings).toBeNull();
    snapshot.source = "runtime";
    expect(runtimeSummary(snapshot).measuredSavings).toBe(snapshot.savings.monthTokens);
  });
});
