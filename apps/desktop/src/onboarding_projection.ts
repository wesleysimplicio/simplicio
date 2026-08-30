import type { DesktopSnapshot } from "./contracts";

export type OnboardingPersona = "personal" | "study" | "create" | "business" | "software" | "explore";
export type OnboardingMode = "simple" | "advanced";

export interface OnboardingTemplate {
  id: OnboardingPersona;
  label: string;
  summary: string;
  defaultCapabilities: string[];
}

export interface OnboardingProjection {
  schema: "onboarding.v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  mode: OnboardingMode;
  templates: OnboardingTemplate[];
  reviewRequired: true;
  createsProvider: false;
  activatesBot: false;
  submitAvailable: boolean;
  reasonCode: string;
}

export function createOnboardingProjection(snapshot: DesktopSnapshot, mode: OnboardingMode = "simple", generatedAt = snapshot.generatedAt): OnboardingProjection {
  const templates: OnboardingTemplate[] = [
    { id: "personal", label: "Personal", summary: "Organize tarefas e contexto do dia.", defaultCapabilities: ["chat.session.create"] },
    { id: "study", label: "Study", summary: "Ler, pesquisar e aprender com provenance.", defaultCapabilities: ["pdf.analyze", "research.run"] },
    { id: "create", label: "Create", summary: "Criar mídia e documentos por Work Item.", defaultCapabilities: ["video.studio", "document.create"] },
    { id: "business", label: "Business", summary: "Operar rotinas com aprovação e budget.", defaultCapabilities: ["browser.open", "automation.draft.create"] },
    { id: "software", label: "Software", summary: "Construir, revisar e validar código.", defaultCapabilities: ["workspace.build", "code.review"] },
    { id: "explore", label: "Explore", summary: "Descobrir capabilities sem ativá-las.", defaultCapabilities: ["capability.registry.read"] },
  ];
  const live = snapshot.source === "runtime" && snapshot.runtime.state === "healthy";
  return { schema: "onboarding.v1", generatedAt, source: snapshot.source, mode, templates, reviewRequired: true, createsProvider: false, activatesBot: false, submitAvailable: live, reasonCode: live ? "onboarding_projection_ready" : "onboarding_projection_unavailable" };
}
