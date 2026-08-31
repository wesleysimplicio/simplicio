import { parseLocalProject, type LocalProject } from "./workbench";

export interface UsageProject extends LocalProject {
  evidenceType: "context" | "usage" | "both";
  lastModifiedEpoch: number | null;
}
export interface UsageProjects {
  schema: "simplicio.desktop-project-usage/v1";
  projects: UsageProject[];
  candidateCount: number;
  roots: Array<{ name: string; path: string }>;
  partial: boolean;
  reasons: string[];
  directoriesVisited: number;
  unavailableRoots?: string[];
}

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("project_discovery_invalid");
  return value as Record<string, unknown>;
}
function count(value: unknown, limit = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0 || value > limit) throw new Error("project_discovery_invalid");
  return value;
}

export function parseUsageProjects(value: unknown): UsageProjects {
  const raw = object(value);
  const scope = object(raw.scope);
  if (raw.schema !== "simplicio.desktop-project-usage/v1" || scope.kind !== "conventional_roots_and_configured_repo"
    || !Array.isArray(raw.projects) || raw.projects.length > 64 || !Array.isArray(raw.roots) || raw.roots.length > 4
    || typeof raw.partial !== "boolean" || !Array.isArray(raw.reasons) || raw.reasons.length > 32) throw new Error("project_discovery_invalid");
  const seen = new Set<string>();
  const projects = raw.projects.map((item: unknown): UsageProject => {
    const entry = object(item);
    const project = parseLocalProject(entry);
    if (seen.has(project.id) || seen.has(project.path) || !["context", "usage", "both"].includes(String(entry.evidenceType))) throw new Error("project_discovery_invalid");
    seen.add(project.id); seen.add(project.path);
    return { ...project, evidenceType: entry.evidenceType as UsageProject["evidenceType"], lastModifiedEpoch: entry.lastModifiedEpoch == null ? null : count(entry.lastModifiedEpoch) };
  });
  const roots = raw.roots.map((item: unknown) => {
    const entry = object(item);
    if (typeof entry.name !== "string" || !entry.name.trim() || entry.name.length > 256
      || typeof entry.path !== "string" || entry.path.length > 4096 || /[\u0000-\u001f]/.test(entry.path)
      || !/^(?:\/(?!\/)|[a-zA-Z]:[\\/])/.test(entry.path)) throw new Error("project_discovery_invalid");
    return { name: entry.name, path: entry.path };
  });
  const candidateCount = count(raw.candidateCount, 4000);
  if (candidateCount < projects.length || (!raw.partial && candidateCount !== projects.length)) throw new Error("project_discovery_invalid");
  const reasons = raw.reasons.map((reason: unknown) => {
    if (typeof reason !== "string" || !/^[a-z_]{1,80}$/.test(reason)) throw new Error("project_discovery_invalid");
    return reason;
  });
  const missing = raw.unavailableRoots ?? [];
  if (!Array.isArray(missing) || missing.length > 4
    || missing.some((name) => typeof name !== "string" || !["Projetos", "Projects", "Desktop", "Configured repository"].includes(name))
    || new Set(missing).size !== missing.length) throw new Error("project_discovery_invalid");
  if (missing.length && !raw.partial) throw new Error("project_discovery_invalid");
  return { schema: "simplicio.desktop-project-usage/v1", projects, candidateCount, roots,
    partial: raw.partial, reasons, directoriesVisited: count(raw.directoriesVisited, 4000), unavailableRoots: missing };
}

export function projectDiscoveryError(cause: unknown): string {
  const code = cause instanceof Error ? cause.message : String(cause);
  if (code === "preview_no_runtime") return "A descoberta automática funciona no app desktop com o Runtime local.";
  if (code === "project_discovery_timeout") return "A descoberta demorou para responder. Você pode informar a pasta manualmente; a consulta pendente não será duplicada.";
  if (code === "desktop_access_not_active") return "Verifique o acesso da conta antes de descobrir as pastas.";
  if (code === "desktop_access_unverified") return "O Runtime não confirmou o acesso da conta nesta consulta. Verifique a conta e tente novamente; nenhuma assinatura foi considerada inativa.";
  return "Não foi possível descobrir as pastas automaticamente. Você ainda pode escolher uma pasta abaixo.";
}
