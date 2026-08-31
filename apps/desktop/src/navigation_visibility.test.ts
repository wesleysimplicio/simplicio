import { describe, expect, it } from "vitest";
import { isNavigationVisible, isView, VIEW_LABELS, type View } from "./workbench";

describe("requested navigation visibility", () => {
  it("hides exactly the requested destinations without deleting routes", () => {
    const hidden: View[] = [
      "orchestration", "computer-use", "voice", "integrations", "mobile", "memory",
      "share-skills", "git", "task-sources", "terminal", "browser", "emulator", "floating",
      "shortcuts", "input", "notifications", "hosts", "servers", "privacy", "advanced", "experimental", "plugins",
    ];
    expect(Object.keys(VIEW_LABELS).filter((view) => isView(view) && !isNavigationVisible(view)).sort()).toEqual([...hidden].sort());
    for (const view of hidden) expect(isView(view)).toBe(true);
    for (const view of ["diagnostics", "general", "permissions", "quick-commands", "tokens", "providers"] as const)
      expect(isNavigationVisible(view)).toBe(true);
  });
});
