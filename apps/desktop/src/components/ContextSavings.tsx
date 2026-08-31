import { useEffect, useRef, useState } from "react";
import { loadDesktopContextReport } from "../bridge";
import { CONTEXT_CONFIDENCE, CONTEXT_EVIDENCE, contextErrorMessage, type ContextReport } from "../context_report";
import "../context_report.css";

export function ContextSavings({ repoPath, autoLoad = false }: { repoPath: string; autoLoad?: boolean }) {
  const [report, setReport] = useState<ContextReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const mounted = useRef(false);
  const scope = repoPath.trim();
  const currentScope = useRef(scope);
  currentScope.current = scope;
  const generation = useRef(0);

  useEffect(() => { mounted.current = true; return () => { mounted.current = false; generation.current += 1; }; }, []);
  useEffect(() => { generation.current += 1; setReport(null); setError(null); }, [scope]);

  async function load() {
    if (pending.current) return;
    pending.current = true;
    const request = ++generation.current;
    const requestedScope = scope;
    setBusy(true);
    setReport(null);
    setError(null);
    try {
      const result = await loadDesktopContextReport(requestedScope);
      if (mounted.current && generation.current === request && currentScope.current === requestedScope) setReport(result);
    } catch (cause) {
      if (mounted.current && generation.current === request && currentScope.current === requestedScope) setError(contextErrorMessage(cause));
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  useEffect(() => {
    if (autoLoad && scope && !busy && !report && !error) void load();
  }, [autoLoad, scope, busy, report, error]);

  const number = (value: number | null) => value === null ? "—" : value.toLocaleString("pt-BR");
  return <section className="panel context-report" aria-label="Economia de contexto">
    <div className="context-report-heading">
      <div><span className="eyebrow">Histórico local do projeto</span><h2>Economia de contexto</h2><p>Todo o histórico da pasta acima. Os filtros de período e sessão se aplicam apenas ao uso registrado.</p></div>
      <button type="button" className="button button-secondary" disabled={busy} onClick={() => void load()}>{busy ? "Consultando economia…" : "Consultar economia de contexto"}</button>
    </div>
    <p className="context-disclaimer">Economia de contexto não é consumo faturado. Este relatório não demonstra, sozinho, preservação do conteúdo nem redução da cobrança do provedor.</p>
    {busy && <p role="status">Consultando e verificando o histórico pelo Runtime…</p>}
    {error && <p role="alert">{error}</p>}
    {!report && !busy && !error && <p className="context-empty">Consulte o histórico desta pasta para ver as reduções de contexto e a qualidade da evidência.</p>}
    {report && <>
      <div className="context-metrics" data-testid="context-metrics">
        <div><span>Reduções registradas</span><strong>{number(report.eventCount ? report.savedTokens : null)}</strong><small>Acumulado bruto do Runtime</small></div>
        <div><span>Referência registrada</span><strong>{number(report.baselineTokens)}</strong><small>Base de comparação do Runtime</small></div>
        <div><span>Com Simplicio</span><strong>{number(report.actualTokens)}</strong><small>Tokens registrados no histórico</small></div>
        <div><span>Diferença líquida</span><strong>{number(report.netTokens)}</strong><small>{report.netTokens !== null && report.netTokens < 0 ? "Mais tokens do que a referência" : "Referência menos tokens registrados"}</small></div>
      </div>
      <p>{report.eventCount.toLocaleString("pt-BR")} {report.eventCount === 1 ? "evento de contexto" : "eventos de contexto"} · {report.ledgerEventCount.toLocaleString("pt-BR")} eventos no histórico.</p>
      <div className="context-proof"><span>{CONTEXT_EVIDENCE[report.baselineKind]}</span><span>Confiança {CONTEXT_CONFIDENCE[report.confidence]}</span></div>
      <p>{report.proof.measured} medidos · {report.proof.estimated} estimados · {report.proof.replayed} replays · {report.proof.benchmark} benchmarks · {report.proof.unavailable} sem classificação. Classificação informada pelo Runtime para o histórico completo.</p>
      {(report.heuristicEventCount > 0 || report.unlabeledEstimateCount > 0) && <p className="context-caution">{report.heuristicEventCount} eventos usam contagem heurística; {report.unlabeledEstimateCount} estimativas não informam o método. Esses valores não equivalem a tokens faturados pelo provedor.</p>}
      {report.llmSpendEventCount > 0 && <p className="context-caution">O histórico também tem {report.llmSpendEventCount} eventos de uso de LLM. O Runtime não separa a referência e o total com Simplicio para este caso; por isso a comparação permanece indisponível.</p>}
      {report.netTokens !== null && report.netTokens !== report.savedTokens && <p className="context-caution">O acumulado bruto de reduções difere do saldo entre referência e uso registrado. Não o trate como economia líquida.</p>}
      <details className="context-digest"><summary>Identificador do relatório</summary><code>{report.reportHash}</code><p>Resumo dos indicadores exibidos; não é assinatura de uma fatura.</p></details>
    </>}
  </section>;
}
