import type { ActivityItem, DesktopSnapshot } from "./contracts";

export interface AutomationSuggestion {
  id: string;
  title: string;
  description: string;
  sourceEventId: string;
  state: "suggested" | "review_required";
}

export interface AutomationProjection {
  schema: "automation.studio/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  suggestions: AutomationSuggestion[];
  activeCount: number | null;
  draftAllowed: boolean;
  reasonCode: string;
}

function suggestion(activity: ActivityItem, index: number): AutomationSuggestion {
  return {
    id: `suggestion-${activity.id}`,
    title: index === 0 ? "Reutilizar contexto recorrente" : "Agrupar validações do Runtime",
    description: "Proposta baseada em recibos; nenhum fluxo será criado sem revisão.",
    sourceEventId: activity.id,
    state: "review_required",
  };
}

export function createAutomationProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): AutomationProjection {
  const suggestions = snapshot.activity.slice(0, 2).map(suggestion);
  const live = snapshot.source === "runtime" && snapshot.runtime.state === "healthy";
  return {
    schema: "automation.studio/v1",
    generatedAt,
    source: snapshot.source,
    suggestions,
    activeCount: live ? 0 : null,
    draftAllowed: live,
    reasonCode: live ? "automation.studio_projection_ready" : "automation.projection_unavailable",
  };
}
