import { describe, expect, it } from "vitest";
import { rememberWorkspaceRoute, viewNavigationEntry } from "./settings_navigation";
import { moveHistory, navigate, type NavigationEntry, type NavigationState } from "./workbench";

const home: NavigationEntry = { view: "home", projectId: null, tokenRepo: "" };
const projectReport: NavigationEntry = { view: "tokens", projectId: "project-a", tokenRepo: "/Projects/Project A" };

describe("settings workspace return", () => {
  it("restores the report view, project and repository after multiple settings pages", () => {
    let history: NavigationState = { entries: [projectReport], index: 0 };
    let workspace = rememberWorkspaceRoute(home, projectReport);
    for (const next of ["settings", "general", "diagnostics", "permissions"] as const) {
      history = navigate(history, viewNavigationEntry(history.entries[history.index], next));
      workspace = rememberWorkspaceRoute(workspace, history.entries[history.index]);
      expect(history.entries[history.index].tokenRepo).toBe("/Projects/Project A");
    }
    history = navigate(history, viewNavigationEntry(history.entries[history.index], workspace.view, workspace));
    expect(history.entries[history.index]).toEqual({ view: "tokens", projectId: "project-a", tokenRepo: "/Projects/Project A" });
    expect(history.entries[moveHistory(history, -1).index].view).toBe("permissions");
    expect(history.entries[moveHistory(moveHistory(history, -1), 1).index]).toEqual(projectReport);
  });

  it("updates the return scope when the repository changes without changing view", () => {
    const first = rememberWorkspaceRoute(home, projectReport);
    const second = rememberWorkspaceRoute(first, { view: "tokens", projectId: "project-b", tokenRepo: "/Projects/Project B" });
    const settings = viewNavigationEntry(second, "settings");
    const workspace = rememberWorkspaceRoute(second, settings);
    expect(viewNavigationEntry(settings, workspace.view, workspace)).toEqual({ view: "tokens", projectId: "project-b", tokenRepo: "/Projects/Project B" });
    expect(first).toEqual(projectReport);
  });

  it("keeps an explicit global report click distinct from returning to the project report", () => {
    const settings = viewNavigationEntry(projectReport, "settings");
    expect(viewNavigationEntry(settings, "tokens")).toEqual({ view: "tokens", projectId: "project-a", tokenRepo: "" });
    expect(viewNavigationEntry(settings, "tokens", projectReport)).toEqual(projectReport);
    expect(viewNavigationEntry(settings, "home")).toEqual({ view: "home", projectId: "project-a", tokenRepo: "" });
  });

  it("returns to a project workspace and preserves an explicitly unselected global route", () => {
    const project: NavigationEntry = { view: "project", projectId: "project-a", tokenRepo: "" };
    expect(viewNavigationEntry(viewNavigationEntry(project, "settings"), "project", project)).toEqual(project);
    expect(viewNavigationEntry(viewNavigationEntry(project, "settings"), "home", home)).toEqual(home);
  });

  it("captures route values without mutating or retaining the caller's mutable route", () => {
    const current = { ...projectReport };
    const workspace = rememberWorkspaceRoute(home, current);
    current.tokenRepo = "/Projects/other";
    expect(workspace.tokenRepo).toBe("/Projects/Project A");
    const restored = viewNavigationEntry(viewNavigationEntry(current, "settings"), "tokens", workspace);
    restored.tokenRepo = "";
    expect(workspace.tokenRepo).toBe("/Projects/Project A");
  });

  it("keeps the return target even when settings visits exhaust bounded history", () => {
    let history: NavigationState = { entries: [projectReport], index: 0 };
    let workspace = rememberWorkspaceRoute(home, projectReport);
    for (let index = 0; index < 60; index += 1) {
      history = navigate(history, viewNavigationEntry(history.entries[history.index], index % 2 ? "diagnostics" : "settings"));
      workspace = rememberWorkspaceRoute(workspace, history.entries[history.index]);
    }
    expect(history.entries).toHaveLength(50);
    expect(viewNavigationEntry(history.entries[history.index], workspace.view, workspace)).toEqual(projectReport);
  });
});
