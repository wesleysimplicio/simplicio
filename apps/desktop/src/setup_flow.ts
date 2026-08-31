import type { DesktopSnapshot } from "./contracts";

export type SetupPhase = "welcome" | "checking" | "planning" | "review" | "installing" | "verifying" | "complete" | "failed";
export type SetupStep = 1 | 2 | 3 | 4;
export type StepState = "pending" | "running" | "complete" | "failed";

const stages = [
  { label: "Conferir Runtime e acesso", detail: "Consultar a sessão e a assinatura pelo Runtime local." },
  { label: "Preparar suas integrações", detail: "Detectar clientes e gerar um plano sem alterar arquivos." },
  { label: "Instalar e registrar o MCP", detail: "Aplicar somente o plano revisado, com backups." },
  { label: "Verificar o resultado", detail: "Consultar novamente o estado e as integrações." },
] as const;

export function setupStages(phase: SetupPhase, failedStep: SetupStep = 1) {
  const completed = phase === "failed" ? failedStep - 1 : ({ welcome: 0, checking: 0, planning: 1, review: 2, installing: 2, verifying: 3, complete: 4 } as const)[phase];
  const running = ({ checking: 1, planning: 2, installing: 3, verifying: 4 } as Partial<Record<SetupPhase, number>>)[phase];
  return stages.map((stage, index) => ({ ...stage, state: (index < completed ? "complete" : phase === "failed" && index + 1 === failedStep ? "failed" : running === index + 1 ? "running" : "pending") as StepState }));
}

export function canConfigureRuntime(snapshot: DesktopSnapshot): boolean {
  return snapshot.access.state === "active" && snapshot.access.identityKnown && snapshot.access.entitlementKnown
    && snapshot.runtime.transport !== "unavailable" && ["healthy", "degraded"].includes(snapshot.runtime.state);
}
