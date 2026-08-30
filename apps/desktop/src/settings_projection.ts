import type { DesktopSnapshot } from "./contracts";

export interface SettingsProjection {
  schema: "settings.projection/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  providers: Array<{ id: string; name: string; state: string; availableActions: string[] }>;
  models: Array<{ id: string; label: string; selectable: boolean; reasonCode: string }>;
  tools: Array<{ id: string; label: string; enabled: boolean; reasonCode: string }>;
  skills: Array<{ id: string; label: string; enabled: boolean; reasonCode: string }>;
  secretPolicy: { bodiesVisible: false; writeOnly: true; rawExport: false };
  reasonCode: string;
}

export function createSettingsProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): SettingsProjection {
  const runtime = snapshot.source === "runtime" && snapshot.runtime.state === "healthy";
  return {
    schema: "settings.projection/v1",
    generatedAt,
    source: snapshot.source,
    providers: snapshot.providers.slice(0, 32).map((provider) => ({ id: provider.id, name: provider.name, state: provider.state, availableActions: provider.availableActions })),
    models: [{ id: "model-runtime-default", label: "Modelo fornecido pelo Runtime", selectable: runtime, reasonCode: runtime ? "model_probe_verified" : "model_probe_unavailable" }],
    tools: [{ id: "tool-runtime-registry", label: "Registry de tools", enabled: runtime, reasonCode: runtime ? "tool_probe_verified" : "tool_probe_unavailable" }],
    skills: [{ id: "skill-runtime-registry", label: "Registry de skills", enabled: runtime, reasonCode: runtime ? "skill_probe_verified" : "skill_probe_unavailable" }],
    secretPolicy: { bodiesVisible: false, writeOnly: true, rawExport: false },
    reasonCode: runtime ? "settings.projection_ready" : "settings.projection_unavailable",
  };
}
