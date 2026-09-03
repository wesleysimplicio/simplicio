import { useState } from "react";
import type { DesktopSnapshot } from "../contracts";
import { Glyph } from "../components/Brand";
import { openDesktopProject } from "../bridge";
import { isNavigationVisible, runtimeSummary, type LocalProject, type View } from "../workbench";
import type { DesktopUsageState } from "../usage_store";
function SessionCenter({ usage }: { usage?: DesktopUsageState }) {
  const changefeed = usage?.changefeed;
  const projection = changefeed?.projection;
  const costProjection = changefeed?.cost_projection;
  const status = changefeed?.connection ?? "offline";
  const statusLabel = status === "live" ? "ao vivo" : status === "reconnecting" ? "reconectando" : status === "stale" ? "último dado conhecido" : "offline";
  const tokens = (value: number | null | undefined) => value === null || value === undefined ? "—" : value.toLocaleString("pt-BR");
  const costValue = costProjection?.totals.actual_cost_usd ?? projection?.totals.cost_usd;
  const cost = costValue === null || costValue === undefined ? "—" : "US$ " + costValue.toFixed(6);

  return <section className="panel session-center" aria-label="Sessão atual">
    <div className="session-center-heading">
      <div><span className="eyebrow">CENTRO DA SESSÃO</span><h2>Uso atual</h2></div>
      <span className={"neutral-badge usage-status usage-" + status}>{statusLabel}</span>
    </div>
    <div className="session-metrics">
      <article><span>Uso registrado</span><strong>{tokens(projection?.totals.total_tokens)}</strong></article>
      <article><span>Baseline</span><strong>{tokens(costProjection?.totals.baseline_tokens)}</strong></article>
      <article><span>Economia comprovada</span><strong>{tokens(costProjection?.totals.saved_tokens)}</strong></article>
      <article><span>Custo registrado</span><strong>{cost}</strong></article>
    </div>
    <p className="token-proof-note">{costProjection ? costProjection.totals.event_count + " evento(s) · cobertura " + costProjection.metadata.coverage.status : projection ? projection.totals.event_count + " evento(s) · cobertura " + projection.metadata.coverage.status : "Aguardando um snapshot comprovado pelo Runtime; nenhum zero foi inferido."}</p>
    <details>
      <summary>Como calculamos</summary>
      <p>O Runtime fornece a projeção redigida. Provider/modelo: {projection?.metadata.coverage.providers.join(", ") || "indisponível"} · pricing: {costProjection?.pricing.version || projection?.metadata.pricing_version || "indisponível"} · motivo: {changefeed?.reason_code || "usage_changefeed_unavailable"}.</p>
    </details>
  </section>;
}


export function WorkbenchHome({ snapshot, project, usage, onAddProject, onViewChange, onRemoveProject, onTokens }:
  { snapshot: DesktopSnapshot; project?: LocalProject; usage?: DesktopUsageState; onAddProject: () => void; onViewChange: (view: View) => void; onRemoveProject: () => void; onTokens: (path?: string) => void }) {
  const status = runtimeSummary(snapshot);
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
      <button type="button" onClick={() => onViewChange("providers")}><Glyph name="providers" size={22} /><strong>Integrações MCP</strong><span>Ver registro e conexão dos harnesses</span><Glyph name="arrow" size={17} /></button>
      <button type="button" onClick={() => void openFolder()} disabled={opening}><Glyph name="folder" size={22} /><strong>{opening ? "Abrindo…" : "Abrir pasta"}</strong><span>No gerenciador de arquivos do sistema</span><Glyph name="external" size={17} /></button>
    </section>
    {openError && <p className="inline-error" role="alert">{openError}</p>}
    <SessionCenter usage={usage} />
    <section className="workbench-section project-boundary"><h2>Seu projeto, com o Runtime</h2><p>Esta lista organiza atalhos locais. Adicionar uma pasta não cria um worktree, não inicia um agente e não altera permissões.</p><p>Execute suas tarefas no harness conectado ao Simplicio MCP. O Runtime continua responsável por contexto, execução e recibos.</p></section>
    <div className="project-remove">{confirmRemove ? <><p>Remover apenas o atalho? Nenhum arquivo da pasta será excluído.</p><button className="button button-secondary" type="button" onClick={() => setConfirmRemove(false)}>Manter projeto</button><button className="button button-secondary" type="button" onClick={onRemoveProject}>Confirmar remoção da lista</button></> : <button className="text-button" type="button" onClick={() => setConfirmRemove(true)}>Remover da lista</button>}</div>
  </div>;

  return <div className="workbench-welcome">
    <div className="welcome-center">
      <img className="welcome-mark" src="/icon.png" width="80" height="80" alt="" />
      <span className="welcome-kicker">SEU ESPAÇO DE TRABALHO</span>
      <h1>Simplicio</h1>
      <p>Seus projetos. Seus agentes.<br />Um Runtime para conectar tudo.</p>
      <div className="welcome-actions"><button className="button button-primary" type="button" onClick={onAddProject}><Glyph name="plus" size={18} />Adicionar projeto</button><button className="button button-secondary" type="button" onClick={() => onViewChange("providers")}><Glyph name="providers" size={18} />Ver integrações</button></div>
      <SessionCenter usage={usage} />
      <div className="welcome-shortcuts"><span><kbd>⌘ / Ctrl K</kbd> Buscar</span>{isNavigationVisible("shortcuts") && <button type="button" onClick={() => onViewChange("shortcuts")}><Glyph name="keyboard" size={14} />Todos os atalhos</button>}</div>
    </div>
    <section className="welcome-resources" aria-label="Acesso rápido">
      {isNavigationVisible("agents") && <button type="button" onClick={() => onViewChange("agents")}><Glyph name="teams" size={20} /><span><strong>Agentes e IDEs</strong><small>{status.installed} detectados · {status.connected} MCP confirmados</small></span><Glyph name="arrow" size={16} /></button>}
      <button type="button" onClick={() => onTokens()}><Glyph name="activity" size={20} /><span><strong>Tokens e economia</strong><small>Consulte uso, períodos e recibos</small></span><Glyph name="arrow" size={16} /></button>
      <button type="button" onClick={() => onViewChange("diagnostics")}><Glyph name="shield" size={20} /><span><strong>Runtime e diagnóstico</strong><small>{status.label} · v{snapshot.runtime.version || "—"}</small></span><Glyph name="arrow" size={16} /></button>
    </section>
    <p className="welcome-footnote">A conexão de cada agente é confirmada pelo Runtime. Sem telemetria, sem números presumidos.</p>
  </div>;
}
