import { useEffect, useRef, useState } from "react";
import { Glyph } from "../components/Brand";
import { ContextSavings } from "../components/ContextSavings";
import { TokenProjects } from "../components/TokenProjects";
import { ConsolidatedTokens } from "../components/ConsolidatedTokens";
import type { UsageProjects } from "../project_usage";
import type { UnifiedUsageProjection } from "../unified_usage";
import type { CostProjection } from "../cost_projection";
import type { DesktopUsageState } from "../usage_store";
import { exportDesktopTokenReport, loadDesktopTokenReport, loadDesktopUnifiedUsage, loadDesktopCostProjection } from "../bridge";
import { TOKEN_PERIODS, tokenErrorMessage, tokenExportErrorMessage, type TokenPeriod, type TokenQuery, type TokenUsageReport } from "../token_usage";

export function TokensScreen({ initialRepoPath = "", projectPaths = [], usage }: { initialRepoPath?: string; projectPaths?: string[]; usage?: DesktopUsageState }) {
  const [discovery, setDiscovery] = useState<UsageProjects | null>(null);
  const [discoveryReady, setDiscoveryReady] = useState(false);
  const [extraPaths, setExtraPaths] = useState<string[]>(initialRepoPath ? [initialRepoPath] : []);
  const [period, setPeriod] = useState<TokenPeriod>("1m");
  const [repoPath, setRepoPath] = useState(initialRepoPath);
  const [allowAutoSelect, setAllowAutoSelect] = useState(!initialRepoPath);
  const [autoContext, setAutoContext] = useState(Boolean(initialRepoPath));
  const [sessionId, setSessionId] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [report, setReport] = useState<TokenUsageReport | null>(null);
  const [unifiedProjection, setUnifiedProjection] = useState<UnifiedUsageProjection | null>(null);
  const [unifiedBusy, setUnifiedBusy] = useState(false);
  const [unifiedError, setUnifiedError] = useState<string | null>(null);
  const [costProjection, setCostProjection] = useState<CostProjection | null>(null);
  const [costBusy, setCostBusy] = useState(false);
  const [costError, setCostError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportPath, setExportPath] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const exportLock = useRef(false);
  const sequence = useRef(0);

  async function load(query: TokenQuery) {
    const request = ++sequence.current;
    setBusy(true);
    setError(null);
    setReport(null);
    setExportPath(null);
    setExportError(null);
    try {
      const next = await loadDesktopTokenReport(query);
      if (request === sequence.current) setReport(next);
    } catch (cause) {
      if (request === sequence.current) setError(tokenErrorMessage(cause));
    } finally {
      if (request === sequence.current) setBusy(false);
    }
  }

  useEffect(() => {
    void load({ timezoneOffsetSeconds: -new Date().getTimezoneOffset() * 60, ...(initialRepoPath ? { repoPath: initialRepoPath } : {}) });
    return () => { sequence.current += 1; };
  }, [initialRepoPath]);

  function invalidate() {
    sequence.current += 1;
    setReport(null);
    setError(null);
    setBusy(false);
    setExportPath(null);
    setExportError(null);
  }

  function submit(path = repoPath) {
    if (exportLock.current) return;
    if (path.trim()) setExtraPaths(paths => paths.includes(path.trim()) ? paths : [...paths.slice(-95), path.trim()]);
    const query: TokenQuery = { timezoneOffsetSeconds: -new Date().getTimezoneOffset() * 60 };
    if (path.trim()) query.repoPath = path.trim();
    if (sessionId.trim()) query.sessionId = sessionId.trim();
    if (period === "custom") {
      query.fromEpoch = Math.floor(new Date(from).getTime() / 1000);
      query.toEpoch = Math.floor(new Date(to).getTime() / 1000);
      if (!Number.isSafeInteger(query.fromEpoch) || !Number.isSafeInteger(query.toEpoch)
        || query.fromEpoch < 0 || query.fromEpoch >= query.toEpoch) {
        invalidate();
        setError(tokenErrorMessage("token_query_invalid"));
        return;
      }
    }
    void load(query);
  }

  async function loadUnifiedUsage() {
    if (unifiedBusy) return;
    setUnifiedBusy(true);
    setUnifiedProjection(null);
    setUnifiedError(null);
    try {
      // Project paths are intentionally not sent to this contract. Runtime owns
      // project identity and redaction; the public v1 query supports session scope.
      const query = sessionId.trim() ? { session_id: sessionId.trim() } : {};
      setUnifiedProjection(await loadDesktopUnifiedUsage(query, repoPath || undefined));
    } catch (cause) {
      setUnifiedError(cause instanceof Error ? cause.message : "unified_usage_unavailable");
    } finally {
      setUnifiedBusy(false);
    }
  }

  async function loadCostProjection() {
    if (costBusy) return;
    setCostBusy(true);
    setCostProjection(null);
    setCostError(null);
    try {
      const query = sessionId.trim() ? { session_id: sessionId.trim() } : {};
      setCostProjection(await loadDesktopCostProjection(query, repoPath || undefined));
    } catch (cause) {
      setCostError(cause instanceof Error ? cause.message : "cost_projection_unavailable");
    } finally {
      setCostBusy(false);
    }
  }

  async function exportReport(format: "json" | "csv") {
    if (!report || exportLock.current) return;
    exportLock.current = true;
    setExporting(true);
    setExportPath(null);
    setExportError(null);
    try {
      const receipt = await exportDesktopTokenReport(report.report_hash, format);
      setExportPath(receipt.path);
    } catch (cause) {
      setExportError(tokenExportErrorMessage(cause));
    } finally {
      exportLock.current = false;
      setExporting(false);
    }
  }

  const selected = report?.periods.find((item) => item.window === period);
  const totals = selected?.totals;
  const hasUsage = Boolean(totals && totals.sample_count > totals.missing_usage_events);
  const metric = (value: number | undefined) => hasUsage && value !== undefined ? value.toLocaleString("pt-BR") : "—";

  return (
    <div className="page secondary-page token-usage-page">
      <section className="page-heading">
        <div><span className="eyebrow">Recibos do Runtime</span><h1>Relatório de tokens</h1><p>Uso registrado por período e sessão. Economia de contexto não é consumo faturado.</p></div>
      </section>
      <section className="panel session-feed-summary" aria-label="Changefeed da sessão">
        <strong>Sessão atual</strong>
        <span>{usage?.changefeed.connection === "live" ? "ao vivo" : usage?.changefeed.connection === "reconnecting" ? "reconectando" : usage?.changefeed.connection === "stale" ? "último dado conhecido" : "offline"}</span>
        <p>{usage?.changefeed.projection ? usage.changefeed.projection.totals.event_count + " evento(s) · " + usage.changefeed.projection.totals.total_tokens.toLocaleString("pt-BR") + " tokens registrados · cobertura " + usage.changefeed.projection.metadata.coverage.status : "Aguardando changefeed comprovado pelo Runtime; nenhum zero foi inferido."}</p>
      </section>
      <ConsolidatedTokens paths={[...projectPaths, ...extraPaths, ...(discovery?.projects.map(project => project.path) ?? [])]} discoveryReady={discoveryReady} discoveryPartial={!discovery || discovery.partial} />
      <section className="individual-token-report" aria-label="Relatório individual">
      <h2>Detalhes por projeto</h2>
      <TokenProjects repoPath={repoPath} allowAutoSelect={allowAutoSelect} onDiscovery={result => { setDiscovery(result); setDiscoveryReady(true); }} onSelect={(path) => {
        if (exportLock.current) return;
        setAllowAutoSelect(false); setAutoContext(true); invalidate(); setRepoPath(path); submit(path);
      }} />
      <form className="panel token-query" onSubmit={(event) => { event.preventDefault(); submit(); }}>
        <label><span id="token-period-label">Período</span><span className="token-select"><select aria-labelledby="token-period-label" value={period} disabled={exporting} onChange={(event) => { setPeriod(event.target.value as TokenPeriod); if (event.target.value === "custom") invalidate(); }}>{TOKEN_PERIODS.map(([id, label]) => <option value={id} key={id}>{label}</option>)}</select></span></label>
        <label>Pasta do projeto (opcional)<input value={repoPath} maxLength={4096} disabled={exporting} onChange={(event) => { setAllowAutoSelect(false); setAutoContext(false); invalidate(); setRepoPath(event.target.value); }} placeholder="Vazio: pasta pessoal" autoComplete="off" spellCheck={false} /></label>
        <label>Sessão (opcional)<input value={sessionId} maxLength={256} disabled={exporting} onChange={(event) => { invalidate(); setSessionId(event.target.value); }} placeholder="Todas as sessões do ledger" autoComplete="off" /></label>
        {period === "custom" && <><label>Início<input type="datetime-local" value={from} required disabled={exporting} onChange={(event) => { invalidate(); setFrom(event.target.value); }} /></label><label>Fim (exclusivo)<input type="datetime-local" value={to} required disabled={exporting} onChange={(event) => { invalidate(); setTo(event.target.value); }} /></label></>}
        <button className="button button-primary" type="submit" disabled={busy || exporting}><Glyph name="refresh" size={17} />{busy ? "Consultando…" : "Consultar uso"}</button>
      </form>
      {error && <section className="panel token-notice" role="alert">{error}</section>}
      {!error && !busy && !selected && <p className="token-notice" role="status">Selecione os filtros e consulte o Runtime para este período.</p>}
      {busy && <p role="status">Consultando o ledger local pelo Runtime…</p>}
      {selected && <>
        <section className="token-metrics" aria-label="Uso registrado">
          {[["Total registrado", totals?.total_tokens], ["Entrada", totals?.input_tokens], ["Saída", totals?.output_tokens], ["Entrada em cache", totals?.cached_input_tokens], ["Raciocínio", totals?.reasoning_tokens], ["Remoto pago informado", totals?.paid_remote_tokens]].map(([label, value]) => <article className="panel token-metric" key={label}><span>{label}</span><strong>{metric(value as number | undefined)}</strong></article>)}
        </section>
        <section className="panel token-evidence">
          <h2>Cobertura e proveniência</h2>
          <p>{totals?.sample_count} {totals?.sample_count === 1 ? "evento" : "eventos"} · {totals?.receipt_count} {totals?.receipt_count === 1 ? "recibo" : "recibos"} · {totals?.missing_usage_events} {totals?.missing_usage_events === 1 ? "evento sem uso informado" : "eventos sem uso informado"}.</p>
          {!hasUsage && <p role="status">Não há uso informado neste recorte. Os traços não representam consumo zero.</p>}
          <p>{new Date(selected.from_epoch * 1000).toLocaleString("pt-BR")} até {new Date(selected.to_epoch * 1000).toLocaleString("pt-BR")} (fim exclusivo).</p>
          <p>O contrato atual não separa estimativas por amostra, modelos ou harnesses e não fornece custo. Os totais são uso registrado, não cobrança nem economia comprovada.</p>
          <code>{report?.report_hash}</code>
          <p>Exportação local para Downloads, sem substituir arquivos existentes.</p>
          <div className="settings-actions"><button className="button button-secondary" type="button" disabled={exporting} onClick={() => void exportReport("json")}>Exportar JSON</button><button className="button button-secondary" type="button" disabled={exporting} onClick={() => void exportReport("csv")}>Exportar CSV</button></div>
          {exporting && <p role="status">Salvando o relatório em Downloads…</p>}
          {exportPath && <p role="status">Exportado para <code>{exportPath}</code></p>}
          {exportError && <p role="alert">{exportError}</p>}
        </section>
      </>}
      <section className="panel token-evidence" aria-label="Uso unificado">
        <h2>Uso unificado</h2>
        <p>Provider, modelo, host e sessão só aparecem quando o Runtime fornecer a projeção versionada e redigida.</p>
        <button className="button button-secondary" type="button" disabled={unifiedBusy || exporting} onClick={() => void loadUnifiedUsage()}>
          {unifiedBusy ? "Consultando projeção…" : "Consultar uso unificado"}
        </button>
        {unifiedError && <p role="status">Projeção indisponível: <code>{unifiedError}</code>. Nenhum zero foi inferido.</p>}
        {unifiedProjection && <div className="token-unified-result">
          <p>{unifiedProjection.rows.length} agrupamento(s) · {unifiedProjection.totals.event_count} evento(s) · cobertura: {unifiedProjection.metadata.coverage.status}</p>
          <p>Tokens registrados: {unifiedProjection.totals.total_tokens.toLocaleString("pt-BR")}; custo: {unifiedProjection.totals.cost_usd === null ? "indisponível" : `US$ ${unifiedProjection.totals.cost_usd.toFixed(6)}`}</p>
          <ul>{unifiedProjection.rows.slice(0, 10).map((row) => <li key={`${row.provider}:${row.model}:${row.host}:${row.session_id ?? "none"}`}>{row.provider} · {row.model} · {row.host} · {row.total_tokens.toLocaleString("pt-BR")} tokens · {row.provenance}</li>)}</ul>
          <code>{unifiedProjection.metadata.report_digest}</code>
        </div>}
      </section>
      <section className="panel token-evidence" aria-label="Custo e economia">
        <h2>Custo, economia e confiança</h2>
        <p>Valores só são exibidos quando o Runtime fornece períodos, pricing e proveniência reconciliados.</p>
        <button className="button button-secondary" type="button" disabled={costBusy || exporting} onClick={() => void loadCostProjection()}>
          {costBusy ? "Consultando custo…" : "Consultar custo e economia"}
        </button>
        {costError && <p role="status">Relatório indisponível: <code>{costError}</code>. Nenhuma economia foi estimada no renderer.</p>}
        {costProjection && <div className="token-cost-result">
          <p>{costProjection.rows.length} agrupamento(s) · pricing: {costProjection.pricing.status} · cobertura: {costProjection.metadata.coverage.status}</p>
          <p>Tokens reais: {costProjection.totals.actual_tokens === null ? "indisponível" : costProjection.totals.actual_tokens.toLocaleString("pt-BR")}; baseline: {costProjection.totals.baseline_tokens === null ? "indisponível" : costProjection.totals.baseline_tokens.toLocaleString("pt-BR")}; economia: {costProjection.totals.saved_tokens === null ? "indisponível" : costProjection.totals.saved_tokens.toLocaleString("pt-BR")}</p>
          <p>Custo real: {costProjection.totals.actual_cost_usd === null ? "indisponível" : `US$ ${costProjection.totals.actual_cost_usd.toFixed(6)}`}; baseline: {costProjection.totals.baseline_cost_usd === null ? "indisponível" : `US$ ${costProjection.totals.baseline_cost_usd.toFixed(6)}`}; economizado: {costProjection.totals.saved_cost_usd === null ? "indisponível" : `US$ ${costProjection.totals.saved_cost_usd.toFixed(6)}`}</p>
          <p>Proveniência: {costProjection.rows.map((row) => row.state).filter((value, index, values) => values.indexOf(value) === index).join(", ") || "indisponível"} · confiança: {costProjection.confidence.actual} · baseline: {costProjection.baseline.values_status} · digest <code>{costProjection.metadata.report_digest}</code></p>
        </div>}
      </section>
      <ContextSavings repoPath={repoPath} autoLoad={autoContext} />
      </section>
    </div>
  );
}
