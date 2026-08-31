const PROOFS = ["measured", "estimated", "replayed", "benchmark", "unavailable"] as const;
type ProofKind = typeof PROOFS[number];
type BaselineKind = ProofKind | "mixed";
type Confidence = "low" | "medium" | "high" | "measured" | "unavailable";

export interface ContextReport {
  schema: "simplicio.desktop-context-report/v1";
  source: "runtime";
  scope: "project_history";
  eventCount: number;
  ledgerEventCount: number;
  llmSpendEventCount: number;
  savedTokens: number;
  baselineTokens: number | null;
  actualTokens: number | null;
  netTokens: number | null;
  baselineKind: BaselineKind;
  confidence: Confidence;
  heuristicEventCount: number;
  unlabeledEstimateCount: number;
  proof: Record<ProofKind, number>;
  reportHash: string;
}

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("context_report_invalid");
  return value as Record<string, unknown>;
}

function count(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) throw new Error("context_report_invalid");
  return value;
}

export function parseContextReport(value: unknown): ContextReport {
  const raw = object(value);
  const invalid = () => { throw new Error("context_report_invalid"); };
  if (raw.schema !== "simplicio.desktop-context-report/v1" || raw.source !== "runtime" || raw.scope !== "project_history"
    || typeof raw.reportHash !== "string" || !/^sha256:[a-f0-9]{64}$/.test(raw.reportHash)) return invalid();
  const eventCount = count(raw.eventCount);
  const ledgerEventCount = count(raw.ledgerEventCount);
  const llmSpendEventCount = count(raw.llmSpendEventCount);
  if (!ledgerEventCount || eventCount + llmSpendEventCount !== ledgerEventCount) return invalid();
  const savedTokens = count(raw.savedTokens);
  if (!eventCount && savedTokens !== 0) return invalid();
  const baselineTokens = raw.baselineTokens === null ? null : count(raw.baselineTokens);
  const actualTokens = raw.actualTokens === null ? null : count(raw.actualTokens);
  let netTokens: number | null = null;
  if (!llmSpendEventCount) {
    if (baselineTokens === null || actualTokens === null || typeof raw.netTokens !== "number"
      || !Number.isSafeInteger(raw.netTokens) || raw.netTokens !== baselineTokens - actualTokens) return invalid();
    netTokens = raw.netTokens;
  } else if (baselineTokens !== null || actualTokens !== null || raw.netTokens !== null) return invalid();
  const baselineKind = raw.baselineKind;
  const confidence = raw.confidence;
  if (typeof baselineKind !== "string" || ![...PROOFS, "mixed"].includes(baselineKind)
    || typeof confidence !== "string" || !["low", "medium", "high", "measured", "unavailable"].includes(confidence)) return invalid();
  const heuristicEventCount = count(raw.heuristicEventCount);
  const unlabeledEstimateCount = count(raw.unlabeledEstimateCount);
  if (heuristicEventCount + unlabeledEstimateCount > ledgerEventCount) return invalid();
  const rawProof = object(raw.proof);
  const proof = Object.fromEntries(PROOFS.map((key) => [key, count(rawProof[key])])) as Record<ProofKind, number>;
  if (Object.values(proof).reduce((sum, n) => sum + n, 0) !== ledgerEventCount) return invalid();
  return { schema: "simplicio.desktop-context-report/v1", source: "runtime", scope: "project_history",
    eventCount, ledgerEventCount, llmSpendEventCount, savedTokens, baselineTokens, actualTokens, netTokens,
    baselineKind: baselineKind as BaselineKind, confidence: confidence as Confidence,
    heuristicEventCount, unlabeledEstimateCount, proof, reportHash: raw.reportHash };
}

/** A timed-out observer does not release a native request or let a different project reuse its result. */
export function createContextReader(
  invoke: (repoPath: string) => Promise<unknown>,
  timeoutMs = 45_000,
): (repoPath: string) => Promise<ContextReport> {
  let pending: { scope: string; promise: Promise<ContextReport> } | null = null;
  return (repoPath) => {
    const scope = repoPath.trim();
    if (pending) return pending.scope === scope ? pending.promise : Promise.reject(new Error("context_report_busy"));
    const native = Promise.resolve().then(() => invoke(scope)).then(parseContextReport);
    const promise = new Promise<ContextReport>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("context_report_timeout")), timeoutMs);
      native.then(
        (report) => { clearTimeout(timer); pending = null; resolve(report); },
        (error: unknown) => { clearTimeout(timer); pending = null; reject(error); },
      );
    });
    pending = { scope, promise };
    return promise;
  };
}

export const CONTEXT_EVIDENCE: Record<BaselineKind, string> = {
  measured: "Evidência marcada como medida", estimated: "Evidência estimada", replayed: "Evidência de replay",
  benchmark: "Evidência de benchmark", mixed: "Evidência mista", unavailable: "Tipo de evidência não informado",
};
export const CONTEXT_CONFIDENCE: Record<Confidence, string> = {
  low: "baixa", medium: "média", high: "alta", measured: "medida pelo Runtime", unavailable: "não informada",
};

export function contextErrorMessage(cause: unknown): string {
  const code = cause instanceof Error ? cause.message : String(cause);
  switch (code) {
    case "context_query_invalid": return "Escolha uma pasta local existente com caminho absoluto e consulte novamente.";
    case "context_ledger_unavailable": return "Esta pasta não tem um histórico local de economia disponível. Escolha o projeto em que o Simplicio foi usado. Nenhum histórico foi criado nesta consulta.";
    case "context_ledger_empty": return "O histórico desta pasta ainda não contém eventos de economia. Ausência de dados não significa consumo zero.";
    case "context_ledger_invalid": return "A verificação de integridade do histórico falhou. Os números não serão exibidos; verifique o ledger pelo Runtime.";
    case "context_report_invalid": return "O Runtime devolveu um relatório incompatível. Nenhuma economia foi assumida.";
    case "context_report_busy": return "A consulta da outra pasta ainda está em andamento. Aguarde sua conclusão antes de consultar esta pasta.";
    case "context_report_timeout": return "O Runtime demorou para responder. A consulta anterior não será duplicada enquanto estiver em andamento.";
    case "desktop_access_not_active": return "Verifique o acesso da conta no Simplicio antes de consultar este relatório.";
    case "desktop_access_unverified": return "O Runtime não confirmou o acesso da conta nesta consulta. Verifique a conta e tente novamente; nenhuma assinatura foi considerada inativa.";
    case "preview_no_runtime": return "Este relatório exige o aplicativo desktop conectado ao Runtime local. A prévia não lê arquivos.";
    default: return "Não foi possível consultar a economia desta pasta. Verifique o Runtime e tente novamente.";
  }
}
