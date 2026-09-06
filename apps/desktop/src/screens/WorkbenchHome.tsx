import { useState } from "react";
import type { DesktopSnapshot } from "../contracts";
import type { ContextReport } from "../context_report";
import { CONTEXT_CONFIDENCE, CONTEXT_EVIDENCE } from "../context_report";
import { Glyph } from "../components/Brand";
import { openDesktopProject } from "../bridge";
import { isNavigationVisible, runtimeSummary, type LocalProject, type View } from "../workbench";
import type { DesktopUsageState } from "../usage_store";
import type { ProviderUsageMetric, ProviderUsageReport } from "../session_idle";
import "../session_center.css";
function SessionCenter({ usage, contextReport }: { usage?: DesktopUsageState; contextReport?: ContextReport | null }) {
  const changefeed = usage?.changefeed;
  const observed = changefeed?.projection;
  const hasData = observed && !["no_data", "unavailable"].includes(observed.metadata.coverage.status);
  const projection = hasData ? observed : null;
  const costProjection = changefeed?.cost_projection;
  const status = changefeed?.connection ?? "offline";
  const tokens = (value: number | null | undefined) => value === null || value === undefined ? "—" : value.toLocaleString("pt-BR");
  const costValue = costProjection
    ? costProjection.totals.actual_cost_usd
    : projection?.totals.cost_usd;
  const cost = costValue === null || costValue === undefined ? "—" : "US$ " + costValue.toFixed(6);
  const idleFinalization = usage?.idleFinalization;
  const providerReports = idleFinalization?.usage.provider_reports ?? [];
  const contextSavings = contextReport && contextReport.netTokens !== null && contextReport.netTokens >= 0
    && contextReport.eventCount > 0 && contextReport.llmSpendEventCount === 0
    ? contextReport.netTokens : null;
  const contextStatus = contextReport && contextReport.eventCount > 0
    ? contextSavings === null ? "comparação indisponível" : "economia consultada"
    : null;
  const statusLabel = status === "live" ? (hasData ? "consultado" : contextStatus ?? "sem dados") : status === "reconnecting" ? "reconectando" : status === "stale" ? "último dado conhecido" : contextStatus ?? "offline";
  const providerToken = (report: ProviderUsageReport, metric: ProviderUsageMetric) => {
    const value = report.totals[metric];
    return value === undefined ? "—" : value.toLocaleString("pt-BR");
  };

  return <section className="panel session-center" aria-label="Uso observado do Runtime">
    <div className="session-center-heading">
      <div><h2>Uso do Runtime</h2></div>
      <span className={"neutral-badge usage-status usage-" + status}>{statusLabel}</span>
    </div>
    <div className="session-metrics">
      <article><span>Uso registrado</span><strong>{tokens(projection?.totals.total_tokens)}</strong></article>
      <article><span>Baseline</span><strong>{tokens(costProjection?.totals.baseline_tokens)}</strong></article>
      <article><span>Economia comprovada</span><strong>{tokens(costProjection?.totals.saved_tokens)}</strong></article>
      <article><span>Custo registrado</span><strong>{cost}</strong></article>
    </div>
    {contextReport && contextReport.eventCount > 0 && <div className="context-savings-callout" data-testid="context-savings-summary">
      <strong>{contextSavings === null ? "Economia líquida indisponível" : contextSavings.toLocaleString("pt-BR") + " tokens poupados"}</strong>
      <span>{contextReport.eventCount.toLocaleString("pt-BR")} eventos de contexto · {CONTEXT_EVIDENCE[contextReport.baselineKind]} · confiança {CONTEXT_CONFIDENCE[contextReport.confidence]}</span>
    </div>}
    <p className="token-proof-note">{costProjection ? costProjection.totals.event_count + " evento(s) · cobertura " + costProjection.metadata.coverage.status : projection ? projection.totals.event_count + " evento(s) · cobertura " + projection.metadata.coverage.status : contextReport && contextReport.eventCount > 0 ? contextReport.eventCount + " evento(s) · contexto verificado pelo Runtime" : "Ainda sem dados verificados."}</p>
    {idleFinalization && <p className="token-proof-note" data-testid="idle-usage-status">
      Sessão após 15 min: {idleFinalization.usage.status === "complete" ? "coleta concluída" : idleFinalization.usage.status === "pending_provider_refresh" ? "coleta parcial" : "indisponível"}.
    </p>}
    {providerReports.length > 0 && <details className="provider-usage-details" data-testid="provider-usage-details">
      <summary>Uso por provedor</summary>
      <div className="provider-usage-list">
        {providerReports.map((report) => <div className="provider-usage-row" key={report.provider}>
          <div className="provider-usage-row-heading"><strong>{report.provider}</strong><span className="neutral-badge">{report.events > 0 ? report.events + " eventos" : report.status}</span></div>
          <small>in {providerToken(report, "input_tokens")} · out {providerToken(report, "output_tokens")} · reason {providerToken(report, "reasoning_tokens")} · cache {providerToken(report, "cache_read_tokens")} / {providerToken(report, "cache_write_tokens")}</small>
        </div>)}
      </div>
    </details>}
    <details>
      <summary>Como calculamos</summary>
      <p>Valores indisponíveis aparecem como —, nunca como zero. Consulta periódica do ledger do Runtime, não das cotas de assinatura. O Runtime fornece a projeção redigida. Provider/modelo: {projection?.metadata.coverage.providers.join(", ") || "indisponível"} · pricing: {costProjection?.pricing.version || projection?.metadata.pricing_version || "indisponível"} · motivo: {changefeed?.reason_code || "usage_changefeed_unavailable"}.</p>
    </details>
  </section>;
}


export function WorkbenchHome({ snapshot, project, usage, contextReport, onAddProject, onViewChange, onRemoveProject, onTokens }:
  { snapshot: DesktopSnapshot; project?: LocalProject; usage?: DesktopUsageState; contextReport?: ContextReport | null; onAddProject: () => void; onViewChange: (view: View) => void; onRemoveProject: () => void; onTokens: (path?: string) => void }) {
  const status = runtimeSummary(snapshot, contextReport);
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  async function openFolder() {
    if (!project || opening) return;
    setOpening(true); setOpenError(null);
    try { await openDesktopProject(project.path); }
    catch { setOpenError("Não foi possível abrir a pasta. Verifique se ela ainda existe e se você tem acesso."); }
    finally { setOpening(false); }
  }

  if (project) return <div className="page project-page">
    <section className="page-heading"><div><span className="eyebrow">PROJETO LOCAL</span><h1>{project.name}</h1><p className="project-path">{project.path}</p></div><span className="neutral-badge"><Glyph name="monitor" size={14} />Este computador</span></section>
    <section className="project-actions" aria-label="Ações do projeto">
      <button type="button" onClick={() => onTokens(project.path)}><Glyph name="activity" size={22} /><strong>Consultar tokens</strong><span>Ledger do Runtime nesta pasta</span><Glyph name="arrow" size={17} /></button>
      <button type="button" onClick={() => onViewChange("providers")}><Glyph name="providers" size={22} /><strong>Integrações MCP</strong><span>Registro e conexão</span><Glyph name="arrow" size={17} /></button>
      <button type="button" onClick={() => void openFolder()} disabled={opening}><Glyph name="folder" size={22} /><strong>{opening ? "Abrindo…" : "Abrir pasta"}</strong><span>No gerenciador de arquivos</span><Glyph name="external" size={17} /></button>
    </section>
    {openError && <p className="inline-error" role="alert">{openError}</p>}
    <SessionCenter usage={usage} contextReport={contextReport} />
    <details className="workbench-section project-boundary"><summary>Sobre os projetos locais</summary><p>Esta lista organiza atalhos locais. Adicionar uma pasta não cria um worktree, não inicia um agente e não altera permissões.</p><p>Execute suas tarefas no harness conectado ao Simplicio MCP. O Runtime continua responsável por contexto, execução e recibos.</p></details>
    <div className="project-remove">{confirmRemove ? <><p>Remover apenas o atalho? Nenhum arquivo da pasta será excluído.</p><button className="button button-secondary" type="button" onClick={() => setConfirmRemove(false)}>Manter projeto</button><button className="button button-secondary" type="button" onClick={onRemoveProject}>Confirmar remoção da lista</button></> : <button className="text-button" type="button" onClick={() => setConfirmRemove(true)}>Remover da lista</button>}</div>
  </div>;

  return <div className="workbench-welcome">
    <div className="welcome-center">
      <img className="welcome-mark" src="/icon.png" width="80" height="80" alt="" />
      <span className="welcome-kicker">SEU ESPAÇO DE TRABALHO</span>
      <h1>Simplicio</h1>
      <p>Projetos e agentes, em um só lugar.</p>
      <div className="welcome-actions"><button className="button button-primary" type="button" onClick={onAddProject}><Glyph name="plus" size={18} />Adicionar projeto</button><button className="button button-secondary" type="button" onClick={() => onViewChange("providers")}><Glyph name="providers" size={18} />Ver integrações</button></div>
      <SessionCenter usage={usage} />
      <div className="welcome-shortcuts"><span><kbd>⌘ / Ctrl K</kbd> Buscar</span>{isNavigationVisible("shortcuts") && <button type="button" onClick={() => onViewChange("shortcuts")}><Glyph name="keyboard" size={14} />Todos os atalhos</button>}</div>
    </div>
    <section className="welcome-resources" aria-label="Acesso rápido">
      {isNavigationVisible("agents") && <button type="button" onClick={() => onViewChange("agents")}><Glyph name="teams" size={20} /><span><strong>Agentes e IDEs</strong><small>{status.installed} detectados · {status.connected} MCP confirmados</small></span><Glyph name="arrow" size={16} /></button>}
      <button type="button" onClick={() => onTokens()}><Glyph name="activity" size={20} /><span><strong>Tokens e economia</strong><small>Consulte uso, períodos e recibos</small></span><Glyph name="arrow" size={16} /></button>
      <button type="button" onClick={() => onViewChange("diagnostics")}><Glyph name="shield" size={20} /><span><strong>Runtime e diagnóstico</strong><small>{status.label} · v{snapshot.runtime.version || "—"}</small></span><Glyph name="arrow" size={16} /></button>
    </section>

  </div>;
}
