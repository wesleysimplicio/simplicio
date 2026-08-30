import type { DesktopSnapshot } from "./contracts";
import { createAutomationProjection, type AutomationSuggestion } from "./automation_projection";

export interface SuggestionInboxProjection {
  schema: "suggestions.inbox/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  suggestions: AutomationSuggestion[];
  actions: { accept: boolean; dismiss: boolean; snooze: boolean };
  reasonCode: string;
}

export function createSuggestionInboxProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): SuggestionInboxProjection {
  const automation = createAutomationProjection(snapshot, generatedAt);
  const live = automation.draftAllowed;
  return { schema: "suggestions.inbox/v1", generatedAt, source: snapshot.source, suggestions: automation.suggestions, actions: { accept: live, dismiss: live, snooze: live }, reasonCode: live ? "suggestions.inbox_ready" : "suggestions.inbox_unavailable" };
}
