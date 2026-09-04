import type { DesktopSnapshot } from "./contracts";

export type SetupPhase = "welcome" | "checking" | "planning" | "review" | "installing" | "reconciling" | "complete" | "failed";
export type SetupStep = 1 | 2 | 3 | 4;
export type StepState = "pending" | "running" | "complete" | "failed";

const stages = [
  { label: "Conferir Runtime e acesso", detail: "Consultar a sessão e a assinatura pelo Runtime local." },
  { label: "Preparar suas integrações", detail: "Detectar clientes e gerar um plano sem alterar arquivos." },
  { label: "Instalar e registrar o MCP", detail: "Aplicar somente o plano revisado e receber um resultado canônico." },
  { label: "Confirmar o resultado", detail: "Usar o recibo canônico devolvido pelo Runtime, sem uma segunda aplicação." },
] as const;

export function setupStages(phase: SetupPhase, failedStep: SetupStep = 1) {
  const completed = phase === "failed" ? failedStep - 1 : ({ welcome: 0, checking: 0, planning: 1, review: 2, installing: 2, reconciling: 3, complete: 4 } as const)[phase];
  const running = ({ checking: 1, planning: 2, installing: 3, reconciling: 4 } as Partial<Record<SetupPhase, number>>)[phase];
  return stages.map((stage, index) => ({ ...stage, state: (index < completed ? "complete" : phase === "failed" && index + 1 === failedStep ? "failed" : running === index + 1 ? "running" : "pending") as StepState }));
}

export function canConfigureRuntime(snapshot: DesktopSnapshot): boolean {
  return snapshot.access.state === "active" && snapshot.access.identityKnown && snapshot.access.entitlementKnown
    && runtimeIsValid(snapshot);
}

export function runtimeIsValid(snapshot: DesktopSnapshot): boolean {
  const runtime = snapshot.runtime;
  return runtime.transport !== "unavailable"
    && runtime.state === "healthy"
    && runtime.deterministic.ready
    && runtime.deterministic.mapper === "canonical"
    && runtime.deterministic.mapCache === "generation_scoped"
    && runtime.deterministic.hookContext === "receipt_only"
    && runtime.optionalFast.required === false
    && runtime.optionalFast.hookInjected === false
    && runtime.optionalFast.status === "not_required";
}
