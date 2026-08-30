import type { DesktopSnapshot } from "./contracts";

export type TeachStepKind = "manual" | "secret" | "optional";

export interface TeachStep {
  id: string;
  kind: TeachStepKind;
  label: string;
  required: boolean;
  redacted: boolean;
  status: "not_recorded" | "recorded" | "review_required";
}

export interface TeachProjection {
  schema: "teach.recorder/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  recordingScope: "explicit_steps_only";
  consentRequired: true;
  steps: TeachStep[];
  actions: { review: boolean; dryRun: boolean; saveDraft: boolean; repair: boolean };
  reasonCode: string;
}

export function createTeachProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): TeachProjection {
  const live = snapshot.source === "runtime" && snapshot.runtime.state === "healthy";
  return {
    schema: "teach.recorder/v1",
    generatedAt,
    source: snapshot.source,
    recordingScope: "explicit_steps_only",
    consentRequired: true,
    steps: [
      { id: "step-1", kind: "manual", label: "Abrir o workspace do projeto", required: true, redacted: false, status: "not_recorded" },
      { id: "step-2", kind: "secret", label: "Credencial ou token", required: false, redacted: true, status: "not_recorded" },
      { id: "step-3", kind: "optional", label: "Validar o resultado", required: false, redacted: false, status: "not_recorded" },
    ],
    actions: { review: live, dryRun: live, saveDraft: live, repair: live },
    reasonCode: live ? "teach.recorder_projection_ready" : "teach.recorder_projection_unavailable",
  };
}
