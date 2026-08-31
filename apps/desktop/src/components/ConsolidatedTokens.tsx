import { useEffect, useRef, useState } from "react";
import { loadDesktopConsolidatedTokens } from "../bridge";
import { collectReportPaths, consolidatedError, consolidatedRange, CONSOLIDATED_PERIODS, PROJECT_STATUS, type ConsolidatedPeriod, type ConsolidatedReport } from "../consolidated_tokens";
import "../consolidated_tokens.css";

const number = (n: number) => n.toLocaleString("pt-BR");
const date = (n: number) => new Date(n * 1000).toLocaleString("pt-BR");

export function ConsolidatedTokens({ paths, discoveryReady, discoveryPartial }: { paths: string[]; discoveryReady: boolean; discoveryPartial: boolean }) {
  const candidates = collectReportPaths(paths);
  const key = JSON.stringify(candidates.paths);
  const [period, setPeriod] = useState<ConsolidatedPeriod>("30d");
  const [loadedReport, setReport] = useState<ConsolidatedReport | null>(null);
  const [reportScope, setReportScope] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const generation = useRef(0);
  const scope = JSON.stringify([key, discoveryReady, period, revision]);
  const report = reportScope === scope ? loadedReport : null;

  useEffect(() => {
    const current = ++generation.current;
    setReport(null); setError(null);
    if (!discoveryReady || !JSON.parse(key).length) { setBusy(false); return; }
    setBusy(true);
    const query = { ...consolidatedRange(period), repoPaths: JSON.parse(key) as string[] };
    void loadDesktopConsolidatedTokens(query).then(next => {
      if (current === generation.current) { setReportScope(scope); setReport(next); }
    }).catch(cause => { if (current === generation.current) setError(consolidatedError(cause)); })
      .finally(() => { if (current === generation.current) setBusy(false); });
    return () => { generation.current += 1; };
  }, [key, discoveryReady, period, revision]);

  const ready = report?.projects.filter(p => p.status === "ready") ?? [];
  const measured = ready.filter(p => p.totals!.sample_count > p.totals!.missing_usage_events);
  const incomplete = discoveryPartial || candidates.omitted > 0 || Boolean(report?.projects.some(p => p.status !== "ready" && p.status !== "duplicate")) || Boolean(report?.totals?.missing_usage_events);
  const totals = report?.totals;
  const hasUsage = Boolean(totals && totals.sample_count > totals.missing_usage_events);
  const ranked = [...measured].sort((a, b) => b.totals!.total_tokens - a.totals!.total_tokens);
  const bars = ranked.slice(0, 8).map(p => ({ label: p.name, path: p.path, total: p.totals!.total_tokens }));
  if (ranked.length > 8) bars.push({ label: `Outros ${ranked.length - 8} projetos`, path: "Demais projetos consultados", total: ranked.slice(8).reduce((n, p) => n + p.totals!.total_tokens, 0) });
  const maximum = Math.max(1, ...bars.map(p => p.total));
  const composition = totals ? [["Entrada", totals.input_tokens, "input"], ["Saída", totals.output_tokens, "output"], ["Raciocínio", totals.reasoning_tokens, "reasoning"]] as const : [];

  return <section className="consolidated-report" aria-label="Relatório consolidado">
    <div className="consolidated-heading"><div><span className="eyebrow">Visão geral</span><h2>Todos os projetos</h2><p>Uso registrado nos projetos encontrados e adicionados, no mesmo intervalo.</p></div>
      <button type="button" className="button button-secondary" disabled={busy || !discoveryReady || !candidates.paths.length} onClick={() => setRevision(n => n + 1)}>Atualizar consolidado</button></div>
    <div className="consolidated-periods" role="group" aria-label="Período do consolidado">{CONSOLIDATED_PERIODS.map(([id, label]) => <button type="button" key={id} aria-pressed={period === id} disabled={busy} onClick={() => setPeriod(id)}>{label}</button>)}</div>
    {!discoveryReady && <p role="status">Aguardando a descoberta de projetos…</p>}
    {discoveryReady && !candidates.paths.length && <p role="status">Nenhum projeto disponível para consolidar. Adicione uma pasta ou atualize a descoberta abaixo.</p>}
    {busy && <p role="status">Consolidando {candidates.paths.length} projetos pelo Runtime… A consulta tem prazo limitado e preserva resultados parciais.</p>}
    {error && <p className="token-notice" role="alert">{error}</p>}
    {report && <>
      <div className="consolidated-coverage"><span className={incomplete ? "coverage-partial" : "coverage-ready"}>{incomplete ? "Cobertura parcial" : "Consulta concluída"}</span><span>{ready.length} de {report.projects.length} pastas consultadas · {measured.length} com uso informado</span></div>
      <p className="consolidated-dates">{date(report.fromEpoch)} → {date(report.toEpoch)} · fim exclusivo</p>
      <div className="token-metrics consolidated-metrics" aria-label="Totais consolidados">{[["Tokens registrados", totals?.total_tokens, hasUsage], ["Entrada em cache", totals?.cached_input_tokens, hasUsage], ["Eventos registrados", totals?.sample_count, totals !== null], ["Recibos", totals?.receipt_count, totals !== null]].map(([label, value, known]) => <article className="panel token-metric" key={String(label)}><span>{label}</span><strong>{known && typeof value === "number" ? number(value) : "—"}</strong></article>)}</div>
      {!hasUsage && <p role="status">Nenhum uso informado neste período. Ausência de telemetria não significa consumo zero.</p>}
      {hasUsage && <div className="consolidated-charts">
        <article className="panel"><h3>Uso por projeto</h3><p>Total registrado · todos os projetos com uso</p><div className="project-bars" role="img" aria-label="Gráfico de barras do total de tokens por projeto; valores detalhados na tabela abaixo">{bars.map(bar => <div className="project-bar" key={bar.path}><div><span title={bar.path}>{bar.label}</span><strong>{number(bar.total)}</strong></div><div className="bar-track"><span style={{ width: `${bar.total / maximum * 100}%` }} /></div></div>)}</div></article>
        <article className="panel"><h3>Composição dos tokens</h3><p>Entrada, saída e raciocínio</p><svg className="composition-chart" viewBox="0 0 200 200" role="img" aria-labelledby="composition-title composition-description"><title id="composition-title">Composição dos tokens registrados</title><desc id="composition-description">{composition.map(([label, value]) => `${label}: ${number(value)}`).join("; ")}. Cache é parte da entrada.</desc><circle cx="100" cy="100" r="72" fill="none" stroke="var(--border, #e5e7eb)" strokeWidth="24" />{composition.map(([label, value, color], index) => {
          const fraction = totals!.total_tokens ? value / totals!.total_tokens : 0;
          const previous = composition.slice(0, index).reduce((n, entry) => n + entry[1], 0);
          return <circle key={label} className={`composition-${color}`} cx="100" cy="100" r="72" pathLength="100" fill="none" strokeWidth="24" strokeDasharray={`${fraction * 100} ${100 - fraction * 100}`} strokeDashoffset={totals!.total_tokens ? -previous / totals!.total_tokens * 100 : 0} transform="rotate(-90 100 100)" />;
        })}<text x="100" y="98" textAnchor="middle">{totals!.total_tokens.toLocaleString("pt-BR", { notation: "compact", maximumFractionDigits: 1 })}</text><text className="composition-caption" x="100" y="119" textAnchor="middle">tokens</text></svg><ul className="composition-legend">{composition.map(([label, value, color]) => <li key={label}><span><i className={`composition-${color}`} />{label}</span><strong>{number(value)}</strong></li>)}</ul><p>Tokens em cache já fazem parte da entrada; não são somados novamente.</p></article>
      </div>}
      <section className="panel consolidated-details"><h3>Cobertura por projeto</h3><div className="consolidated-table-scroll" role="region" aria-label="Tabela de projetos" tabIndex={0}><table><thead><tr><th scope="col">Projeto</th><th scope="col">Estado</th><th scope="col">Tokens</th><th scope="col">Eventos sem uso</th></tr></thead><tbody>{report.projects.map(p => <tr key={p.path}><th scope="row">{p.name}<small>{p.path}</small></th><td>{PROJECT_STATUS[p.status]}</td><td>{p.totals && p.totals.sample_count > p.totals.missing_usage_events ? number(p.totals.total_tokens) : "—"}</td><td>{p.totals ? number(p.totals.missing_usage_events) : "—"}</td></tr>)}</tbody></table></div></section>
      <details className="consolidated-method"><summary>Escopo e critérios do relatório</summary><p>7 e 30 dias são intervalos corridos de 24 horas; 3, 6 e 12 meses seguem o calendário local, ajustando o último dia do mês. Todas as sessões são incluídas. O horário final é fixado antes da consulta dos projetos.</p><p>Apenas relatórios válidos entram nos totais. Aliases do mesmo ledger são excluídos; eventos copiados para bancos independentes não podem ser deduplicados pelo contrato atual. Não há séries diárias, custo ou cobrança neste contrato.</p><p>A descoberta é limitada aos locais informados abaixo e aos projetos adicionados, até 96 caminhos. Não representa uma varredura completa do computador. {discoveryPartial && "A descoberta não concluiu todos os locais."} {candidates.omitted > 0 && `${candidates.omitted} caminhos ficaram fora do limite.`}</p><p>A economia de contexto apresentada abaixo usa o histórico do projeto selecionado e não faz parte deste consolidado por período.</p><code>{report.reportHash}</code></details>
    </>}
  </section>;
}
