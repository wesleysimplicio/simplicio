import type { DesktopSnapshot } from "./contracts";
import { providerRegistry } from "./provider_registry";
import { isReferenceSettingsView, REFERENCE_LABELS, type ReferenceSettingsView } from "./reference_screens";

export type View = ReferenceSettingsView | "home" | "project" | "agents" | "models" | "general" | "shortcuts" | "diagnostics" | "setup"
  | "today" | "chats" | "teams" | "automations" | "apps" | "bot" | "providers" | "tokens" | "activity" | "memory" | "settings";

export const VIEW_LABELS: Record<View, string> = {
  ...REFERENCE_LABELS,
  home: "Início", project: "Projeto", agents: "Agentes e IDEs", models: "Modelos e skills", setup: "Instalação guiada",
  general: "Aparência", shortcuts: "Atalhos", diagnostics: "Runtime e diagnóstico",
  providers: "Integrações MCP", tokens: "Relatório de tokens", activity: "Atividade",
  memory: "Memória", settings: "Conta Simplicio", today: "Hoje", chats: "Conversas",
  teams: "Equipes", automations: "Automações", apps: "Aplicativos", bot: "Central de agentes",
};

export function isView(value: string | null): value is View {
  return value !== null && Object.prototype.hasOwnProperty.call(VIEW_LABELS, value);
}

export function isSettingsView(view: View): boolean {
  return isReferenceSettingsView(view) || ["settings", "agents", "providers", "models", "general", "shortcuts", "diagnostics", "memory"].includes(view);
}

export function searchMatches(text: string, query: string): boolean {
  const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
  return normalize(text).includes(normalize(query.trim()));
}

export interface NavigationEntry {
  view: View;
  projectId: string | null;
  tokenRepo: string;
}
export interface NavigationState { entries: NavigationEntry[]; index: number }

export function navigate(state: NavigationState, entry: NavigationEntry): NavigationState {
  const current = state.entries[state.index];
  if (current && current.view === entry.view && current.projectId === entry.projectId && current.tokenRepo === entry.tokenRepo) return state;
  // Capture the route scope, not a mutable reference to the caller's selection.
  const destination = { view: entry.view, projectId: entry.projectId, tokenRepo: entry.tokenRepo };
  const entries = [...state.entries.slice(0, state.index + 1), destination].slice(-50);
  return { entries, index: entries.length - 1 };
}

export function moveHistory(state: NavigationState, direction: -1 | 1): NavigationState {
  return { ...state, index: Math.max(0, Math.min(state.entries.length - 1, state.index + direction)) };
}

export interface LocalProject { id: string; name: string; path: string }
export interface WorkbenchPreferences {
  density: "comfortable" | "compact";
  showProjectPaths: boolean;
  rememberProject: boolean;
}
export interface WorkbenchState {
  schema: "simplicio.desktop-workbench/v1";
  projects: LocalProject[];
  selectedProjectId: string | null;
  preferences: WorkbenchPreferences;
}

export const WORKBENCH_KEY = "simplicio.desktop.workbench.v1";
export const DEFAULT_PREFERENCES: WorkbenchPreferences = { density: "comfortable", showProjectPaths: false, rememberProject: true };
export const MAX_PROJECTS = 32;

export function emptyWorkbench(): WorkbenchState {
  return { schema: "simplicio.desktop-workbench/v1", projects: [], selectedProjectId: null, preferences: { ...DEFAULT_PREFERENCES } };
}

export function parseLocalProject(value: unknown): LocalProject {
  if (typeof value !== "object" || value === null) throw new Error("project_invalid");
  const project = value as Record<string, unknown>;
  if (typeof project.id !== "string" || !/^project-[a-f0-9]{64}$/.test(project.id)
    || typeof project.name !== "string" || !project.name.trim() || project.name.length > 256
    || typeof project.path !== "string" || project.path.length > 4096 || /[\u0000-\u001f]/.test(project.path)
    || !(/^(?:\/(?!\/)|[a-zA-Z]:[\\/])/.test(project.path))) throw new Error("project_invalid");
  return { id: project.id, name: project.name, path: project.path };
}

/** Local bookmarks and visual preferences only; never Runtime workspace authority. */
export function parseWorkbench(raw: string | null): WorkbenchState {
  const state = emptyWorkbench();
  if (!raw || raw.length > 180_000) return state;
  try {
    const value = JSON.parse(raw);
    if (value?.schema !== state.schema || !Array.isArray(value.projects)) return state;
    for (const candidate of value.projects.slice(0, MAX_PROJECTS)) {
      try {
        const project = parseLocalProject(candidate);
        if (!state.projects.some((item) => item.id === project.id || item.path === project.path)) state.projects.push(project);
      } catch { /* A corrupt bookmark must not prevent the app from opening. */ }
    }
    const preferences = value.preferences;
    if (preferences?.density === "compact") state.preferences.density = "compact";
    if (typeof preferences?.showProjectPaths === "boolean") state.preferences.showProjectPaths = preferences.showProjectPaths;
    if (typeof preferences?.rememberProject === "boolean") state.preferences.rememberProject = preferences.rememberProject;
    if (state.preferences.rememberProject && state.projects.some((item) => item.id === value.selectedProjectId)) {
      state.selectedProjectId = value.selectedProjectId;
    }
    return state;
  } catch { return state; }
}

export function loadWorkbench(): WorkbenchState {
  try { return parseWorkbench(typeof window === "undefined" ? null : window.localStorage.getItem(WORKBENCH_KEY)); }
  catch { return emptyWorkbench(); }
}

export function runtimeSummary(snapshot: DesktopSnapshot) {
  const states = { healthy: "Runtime online", starting: "Runtime iniciando", degraded: "Runtime degradado", offline: "Runtime offline" };
  const providers = providerRegistry(snapshot.providers);
  return {
    label: states[snapshot.runtime.state],
    healthy: snapshot.runtime.state === "healthy",
    connected: providers.filter((provider) => provider.state === "connected").length,
    installed: providers.filter((provider) => provider.installState === "installed").length,
    measuredSavings: snapshot.savings.proofKind === "measured" && snapshot.savings.ledgerStatus === "valid"
      ? snapshot.savings.monthTokens : null,
  };
}
