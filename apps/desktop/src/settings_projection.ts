import type { DesktopSnapshot } from "./contracts";
import { providerRegistry } from "./provider_registry";

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
  const bots = snapshot.source === "runtime" && snapshot.botCenter?.source === "runtime" ? snapshot.botCenter.bots.slice(0, 32) : [];
  const models = [...new Set(bots.filter((bot) => bot.model).map((bot) => `${bot.provider ?? "provider não informado"} · ${bot.model}`))];
  const tools = [...new Set(bots.flatMap((bot) => bot.toolset))].slice(0, 128);
  const skills = [...new Set(bots.flatMap((bot) => bot.skills))].slice(0, 128);
  return {
    schema: "settings.projection/v1",
    generatedAt,
    source: snapshot.source,
    providers: providerRegistry(snapshot.providers).slice(0, 32).map((provider) => ({ id: provider.id, name: provider.name, state: provider.state, availableActions: provider.availableActions })),
    models: models.map((label) => ({ id: label, label, selectable: false, reasonCode: "runtime_reported_read_only" })),
    tools: tools.map((label) => ({ id: label, label, enabled: false, reasonCode: "runtime_reported_read_only" })),
    skills: skills.map((label) => ({ id: label, label, enabled: false, reasonCode: "runtime_reported_read_only" })),
    secretPolicy: { bodiesVisible: false, writeOnly: true, rawExport: false },
    reasonCode: bots.length ? "settings.runtime_reported_inventory" : "settings.model_inventory_unavailable",
  };
}
