import { isSettingsView, type NavigationEntry, type View } from "./workbench";

/** Keep the full workspace route while visiting any number of settings pages. */
export function rememberWorkspaceRoute(previous: NavigationEntry, current: NavigationEntry): NavigationEntry {
  return isSettingsView(current.view) ? previous : { ...current };
}

/** Explicit workspace return restores scope; ordinary report navigation remains global. */
export function viewNavigationEntry(current: NavigationEntry, next: View, restore?: NavigationEntry): NavigationEntry {
  if (restore && restore.view === next && !isSettingsView(next)) return { ...restore };
  return {
    view: next,
    projectId: current.projectId,
    tokenRepo: isSettingsView(next) ? current.tokenRepo : "",
  };
}
