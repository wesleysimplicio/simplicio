import { useCallback, useEffect, useRef, useState } from "react";
import { Glyph } from "../components/Brand";
import { loadDesktopExecutionReport } from "../bridge";
import { downloadExecutionReport } from "../execution_report";
import type {
  ExecutionReport,
  ReportTask,
  ReportTokenUsage,
  ReportValidation,
} from "../execution_report";

function number(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("pt-BR");
}

function duration(value: number | null): string {
  if (value === null) return "—";
  if (value < 1_000) return value.toLocaleString("pt-BR") + " ms";
  const seconds = value / 1_000;
  if (seconds < 60) return seconds.toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " s";
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return minutes + " min" + (rest ? " " + rest + " s" : "");
}

function cost(value: number | null): string {
  if (value === null) return "—";
  return (value / 1_000_000).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 6,
  });
}

function dateTime(value: number | null): string {
  if (value === null) return "horário não disponível";
  return new Date(value * 1_000).toLocaleString("pt-BR");
}

function outcomeLabel(value: string): string {
  switch (value) {
    case "COMPLETE":
    case "VERIFIED":
    case "PASSED":
      return "concluída";
    case "FAIL":
    case "FAILED":
      return "falhou";
    case "SKIP":
    case "SKIPPED":
      return "ignorada";
    case "IN_PROGRESS":
      return "em andamento";
    default:
      return "não verificada";
  }
}

function outcomeTone(value: string): string {
  switch (value) {
    case "COMPLETE":
    case "VERIFIED":
    case "PASSED":
      return "success";
    case "FAIL":
    case "FAILED":
      return "danger";
    case "IN_PROGRESS":
    case "OPEN":
      return "warning";
    default:
      return "neutral";
  }
}

function validationTone(value: string): string {
  switch (value) {
    case "passed": return "success";
    case "failed": return "danger";
    case "partial":
    case "not_run": return "warning";
    default: return "neutral";
  }
}

type ReportConnection = "connecting" | "live" | "stale" | "offline";

function connectionLabel(value: ReportConnection): string {
  switch (value) {
    case "live": return "Atualização ao vivo";
    case "stale": return "Dados desatualizados";
    case "offline": return "Runtime indisponível";
    default: return "Reconectando ao Runtime";
  }
}

function coverageLabel(value: string): string {
  switch (value) {
    case "complete": return "cobertura completa";
    case "partial": return "cobertura parcial";
    case "no_data": return "sem dados";
    default: return "cobertura indisponível";
  }
}

function tokenSummary(tokens: ReportTokenUsage): string {
  const cacheRead = tokens.cacheRead === null
    ? "cache lido —"
    : "cache lido " + tokens.cacheRead.toLocaleString("pt-BR") + (tokens.cacheReadProvenance ? " (" + tokens.cacheReadProvenance + ")" : "");
  const cacheWrite = tokens.cacheWrite === null
    ? "cache escrito —"
    : "cache escrito " + tokens.cacheWrite.toLocaleString("pt-BR") + (tokens.cacheWriteProvenance ? " (" + tokens.cacheWriteProvenance + ")" : "");
  const reasoning = tokens.reasoning === null
    ? "raciocínio —"
    : "raciocínio " + tokens.reasoning.toLocaleString("pt-BR") + (tokens.reasoningSemantics !== "unknown" ? " (" + tokens.reasoningSemantics + ")" : "");
  return [
    tokens.total === null ? "total —" : tokens.total.toLocaleString("pt-BR") + " tokens",
    cacheRead,
    cacheWrite,
    reasoning,
  ].join(" · ");
}

function validationLabel(validation: ReportValidation): string {
  const checks = validation.checks === null ? "quantidade não registrada" : validation.checks.toLocaleString("pt-BR");
  const failures = validation.failures === null ? "quantidade não registrada" : validation.failures.toLocaleString("pt-BR");
  const coverage = validation.coverageStatus === "partial" ? " · cobertura parcial" : "";
  if (validation.status === "passed") {
    if (validation.executed === 0 || validation.checks === 0) return "nenhuma verificação executada";
    return (validation.passed === null || validation.passed === undefined ? checks : validation.passed.toLocaleString("pt-BR")) + " verificações aprovadas";
  }
  if (validation.status === "failed" || (validation.failures !== null && validation.failures > 0)) return failures + " falha(s) em " + checks + " verificações" + coverage;
  if (validation.status === "partial") return failures + " falha(s); validação parcial";
  if (validation.status === "not_run") return "não executada";
  return "não disponível" + coverage;
}

function aggregateMetric(label: string, value: number | null, rollup: string | undefined): string {
  if (value === null) return label + " —";
  return label + " " + number(value) + (rollup === "partial" ? " (subtotal parcial)" : "");
}

function costLabel(consolidated: { costMicrousdSum: number | null; costRollup: string; costStatus: string }): string {
  if (consolidated.costMicrousdSum === null) return "sem preço confirmado";
  const origin = consolidated.costStatus === "known"
    ? "preço confirmado"
    : consolidated.costStatus === "estimated"
      ? "estimativa"
      : consolidated.costStatus === "mixed"
        ? "origens mistas"
        : "origem não informada";
  return consolidated.costRollup === "partial" ? origin + " · cobertura parcial" : origin;
}

function projectLabel(path: string): string {
  const normalized = path.replace(/[\\/]+$/, "");
  return normalized.split(/[\\/]/).pop() || "escopo local";
}

function Metric({ label, value, detail, tone = "" }: { label: string; value: string; detail: string; tone?: string }) {
  return (
    <div className={"report-metric " + tone}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function TaskDetails({ task }: { task: ReportTask }) {
  return (
    <div className="report-task-details">
      <div className="report-task-facts">
        <div><span>Duração</span><strong>{duration(task.wallMs)}</strong></div>
        <div><span>Tokens</span><strong>{number(task.tokens.total)}</strong><small>{tokenSummary(task.tokens)}</small></div>
        <div><span>Custo</span><strong>{cost(task.tokens.costMicrousd)}</strong><small>{task.tokens.costStatus} · {task.tokens.costProvenance}</small></div>
        <div><span>Validação</span><strong>{validationLabel(task.validation)}</strong><small>{task.validation.source}</small></div>
      </div>

      <div className="report-task-meta-grid">
        <div><span>Modelo</span><strong>{task.model || "—"}</strong><small>{task.provider || "provedor não informado"}</small></div>
        <div><span>Engine</span><strong>{task.engine || "indisponível"}</strong><small>{task.engineVersion || "versão não registrada"}</small></div>
        <div><span>Fallback</span><strong>{task.fallbackReason ? "fallback registrado" : "sem fallback registrado"}</strong><small>{task.fallbackReason || "não informado"}</small></div>
        <div><span>Sessões</span><strong>{task.sessionIds?.length ? task.sessionIds.join(" · ") : "—"}</strong><small>{task.taskRunId ? "run " + task.taskRunId : "identidade de run não informada"}</small></div>
      </div>

      <div className="report-task-trace">
        <span>Conclusão: {task.completionVerdict || "não verificada"}</span>
        <span>Tentativa: {task.attemptId || "não informada"}</span>
        <span>Parent span: {task.parentSpanId || "não informado"}</span>
        <span>Recibos: {task.receipts?.length ? task.receipts.join(" · ") : "não registrados"}</span>
        {task.unresolved?.length ? <span>Não resolvido: {task.unresolved.join(" · ")}</span> : null}
      </div>

      <div className="report-lanes">
        <section className="report-lane">
          <div className="report-lane-heading"><h3>Etapas</h3><span>{task.stages.length || "—"}</span></div>
          {task.stages.length === 0
            ? <p className="report-muted">Etapas não registradas.</p>
            : <ol className="report-stage-list">{task.stages.map((stage) => (
              <li key={stage.id}>
                <div className="report-stage-marker" />
                <div className="report-line-copy"><strong>{stage.name}</strong><span>{stage.id} · {stage.status} · {duration(stage.wallMs)}</span><small>{tokenSummary(stage.tokens)}</small></div>
                <span className="report-line-count">{stage.attemptCount > 1 ? stage.attemptCount + " tent." : ""}</span>
              </li>
            ))}</ol>}
        </section>

        <section className="report-lane">
          <div className="report-lane-heading"><h3>Ferramentas</h3><span>{task.tools.length || "—"}</span></div>
          {task.tools.length === 0
            ? <p className="report-muted">Ferramentas não registradas.</p>
            : <ul className="report-tool-list">{task.tools.map((tool) => (
              <li key={tool.name}>
                <div><strong>{tool.name}</strong><span>{tool.status} · {duration(tool.wallMs)}</span></div>
                <b>{tool.invocations}×</b>
              </li>
            ))}</ul>}
        </section>

        <section className="report-lane">
          <div className="report-lane-heading"><h3>Falhas e retries</h3><span>{task.errors.length + task.retries.length || "—"}</span></div>
          {task.errors.length === 0 && task.retries.length === 0
            ? <p className="report-muted">Nenhuma falha ou retry registrado.</p>
            : <ul className="report-event-list">
              {task.errors.map((error, index) => <li className="report-event-error" key={"error-" + error.code + index}><strong>{error.code}</strong><span>{error.stageId ? "etapa " + error.stageId : "etapa não informada"}{error.retryable === true ? " · retryável" : ""}</span></li>)}
              {task.retries.map((retry) => <li className="report-event-retry" key={"retry-" + retry.attempt}><strong>Tentativa {retry.attempt}</strong><span>{retry.reasonCode} · {retry.status} · {duration(retry.wallMs)}</span></li>)}
            </ul>}
        </section>
      </div>

      <div className={"report-validation report-validation-" + validationTone(task.validation.status)}>
        <div><span className="eyebrow">Gate de validação</span><strong>{validationLabel(task.validation)}</strong></div>
        <span>{task.validation.notes.length ? task.validation.notes.join(" · ") : task.validation.source}</span>
      </div>
      <div className="report-task-footer">
        <span>{coverageLabel(task.coverage.status)}</span>
        <span>{task.operators.length ? task.operators.join(" · ") : "operadores não registrados"}</span>
      </div>
    </div>
  );
}

export function ReportsScreen({ repoPath = "" }: { repoPath?: string }) {
  const [report, setReport] = useState<ExecutionReport | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | undefined>();
  const [historyStatus, setHistoryStatus] = useState("all");
  const [historyPeriod, setHistoryPeriod] = useState("all");
  const [taskFilter, setTaskFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connection, setConnection] = useState<ReportConnection>("connecting");
  const [lastRefreshAt, setLastRefreshAt] = useState<number | null>(null);
  const request = useRef(0);
  const inFlight = useRef<{ key: string; promise: Promise<void> } | null>(null);
  const hasReport = useRef(false);
  const queryKey = JSON.stringify([repoPath, selectedRunId || null]);
  const previousQueryKey = useRef(queryKey);

  useEffect(() => {
    if (previousQueryKey.current === queryKey) return;
    previousQueryKey.current = queryKey;
    request.current += 1;
    setReport(null);
    setBusy(false);
    setError(null);
    setConnection("connecting");
    setLastRefreshAt(null);
    hasReport.current = false;
  }, [queryKey]);

  const refresh = useCallback(() => {
    const key = repoPath + "\\u0000" + (selectedRunId || "");
    if (inFlight.current?.key === key) return inFlight.current.promise;
    const current = ++request.current;
    const operation = (async () => {
      setBusy(true);
      setError(null);
      if (!hasReport.current) setConnection("connecting");
      try {
        const next = await loadDesktopExecutionReport(repoPath || undefined, selectedRunId);
        if (current === request.current) {
          setReport(next);
          hasReport.current = next.present;
          setConnection("live");
          setLastRefreshAt(Math.floor(Date.now() / 1000));
        }
      } catch {
        if (current === request.current) {
          setConnection(hasReport.current ? "stale" : "offline");
          setError("execution_report_unavailable");
        }
      } finally {
        if (current === request.current) setBusy(false);
      }
    })();
    inFlight.current = { key, promise: operation };
    void operation.finally(() => {
      if (inFlight.current?.promise === operation) inFlight.current = null;
    });
    return operation;
  }, [repoPath, selectedRunId]);

  useEffect(() => {
    let disposed = false;
    let timer: number | undefined;
    const native = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    const poll = async () => {
      await refresh();
      if (native && !disposed) timer = window.setTimeout(() => { void poll(); }, 5_000);
    };
    void poll();
    return () => {
      disposed = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [refresh]);

  function exportReport() {
    if (report) downloadExecutionReport(report);
  }

  if (!report && busy) {
    return <div className="page secondary-page reports-page"><div className="report-loading" role="status" aria-live="polite"><span className="eyebrow">Telemetria local</span><h1>Relatórios de execução</h1><p>Consultando o último relatório do Runtime…</p><div className="report-loading-bar" /></div></div>;
  }

  if (!report) {
    return <div className="page secondary-page reports-page"><section className="page-heading"><div><span className="eyebrow">Telemetria local</span><h1>Relatórios de execução</h1><p>Resumo por tarefa com evidência de etapas, ferramentas, custo e validação.</p></div><button className="button button-secondary" type="button" onClick={() => void refresh()} disabled={busy}><Glyph name="refresh" size={16} />{busy ? "Atualizando…" : "Tentar novamente"}</button></section><p className="inline-error" role="alert">Não foi possível ler o relatório do Runtime. Tente novamente quando o Runtime estiver disponível.</p></div>;
  }

  if (!report.present) {
    return <div className="page secondary-page reports-page"><section className="page-heading"><div><span className="eyebrow">Telemetria local</span><h1>Relatórios de execução</h1><p>Resumo por tarefa com evidência de etapas, ferramentas, custo e validação.</p></div><button className="button button-secondary" type="button" onClick={() => void refresh()} disabled={busy}><Glyph name="refresh" size={16} />Atualizar</button></section><section className="panel report-empty" role="status"><div className="report-empty-mark"><Glyph name="activity" size={24} /></div><h2>Nenhum relatório registrado</h2><p>O Runtime não registrou um relatório local para este escopo.</p><p className="report-muted">O Runtime só mostra números quando há recibo local. Dados ausentes permanecem como indisponíveis.</p></section></div>;
  }

  const { consolidated } = report;
  const statusTone = outcomeTone(report.status);
  const reportScope = repoPath ? projectLabel(repoPath) : "escopo local padrão";
  const periodSeconds = historyPeriod === "24h" ? 86_400 : historyPeriod === "7d" ? 604_800 : historyPeriod === "30d" ? 2_592_000 : null;
  const historyCutoff = periodSeconds === null ? null : report.fetchedAtUnix - periodSeconds;
  const visibleHistory = report.history.filter((entry) => {
    const stateMatches = historyStatus === "all" || entry.status === historyStatus;
    const periodMatches = historyCutoff === null || (entry.recordedAtUnix !== null && entry.recordedAtUnix >= historyCutoff);
    return stateMatches && periodMatches;
  });
  const normalizedTaskFilter = taskFilter.trim().toLocaleLowerCase("pt-BR");
  const visibleTasks = report.tasks.filter((task) => {
    if (!normalizedTaskFilter) return true;
    return [task.title, task.issue || "", task.taskId]
      .join(" ")
      .toLocaleLowerCase("pt-BR")
      .includes(normalizedTaskFilter);
  });

  return (
    <div className="page secondary-page reports-page">
      <section className="page-heading reports-heading">
        <div>
          <span className="eyebrow">Telemetria local · {report.executionProfile}</span>
          <h1>Relatórios de execução</h1>
          <p>Um registro por tarefa, com etapas e validações separadas do sucesso do modelo.</p>
        </div>
        <div className="reports-heading-actions">
          <span className={"report-status report-status-" + statusTone}>{outcomeLabel(report.status)}</span>
          <button className="button button-secondary" type="button" onClick={() => void refresh()} disabled={busy}><Glyph name="refresh" size={16} />{busy ? "Atualizando…" : "Atualizar"}</button>
          <button className="button button-primary" type="button" onClick={exportReport}><Glyph name="external" size={16} />Exportar JSON</button>
        </div>
      </section>

      <section className="report-context" aria-label="Escopo do relatório">
        <div><span className="report-context-dot" /><strong>{reportScope}</strong><span>·</span><span>run {report.runId}</span></div>
        <div className="report-context-meta">
          <span>Atualizado {dateTime(report.fetchedAtUnix)} · revisão {report.revision || "não informada"}</span>
          <span>Engine {report.engine || "não informada"}{report.engineVersion ? " · " + report.engineVersion : ""} · {report.fallbackReason || "sem fallback registrado"}</span>
          <span>Decisão Loop: {typeof report.loopDecision?.verdict === "string" ? report.loopDecision.verdict : "não informada"}</span>
        </div>
      </section>

      <div className={"report-sync report-sync-" + connection} role="status" aria-live="polite">
        <div><span className="report-sync-dot" /><strong>{connectionLabel(connection)}</strong><span>{lastRefreshAt === null ? "aguardando leitura" : "última leitura " + dateTime(lastRefreshAt)}</span></div>
        {connection === "stale" ? <span>{error ? "A leitura mais recente falhou; os dados exibidos são da última revisão confirmada." : "Aguardando reconexão; não há novos dados confirmados."}</span> : null}
        {connection === "stale" || connection === "offline" ? <button className="text-button" type="button" onClick={() => void refresh()} disabled={busy}>{busy ? "Reconectando…" : "Reconectar"}</button> : null}
      </div>

      <section className="panel report-history-shell" aria-labelledby="report-history-title">
        <div className="report-history-controls">
          <label className="report-filter-field report-filter-field-wide">
            <span>Tarefa</span>
            <input value={taskFilter} onChange={(event) => setTaskFilter(event.target.value)} placeholder="Título, issue ou task id" aria-label="Filtrar tarefas" />
          </label>
          <label className="report-filter-field">
            <span>Estado</span>
            <select value={historyStatus} onChange={(event) => setHistoryStatus(event.target.value)} aria-label="Filtrar histórico por estado">
              <option value="all">Todos os estados</option>
              <option value="COMPLETE">Concluídos</option>
              <option value="FAIL">Falhos</option>
              <option value="OPEN">Em andamento</option>
              <option value="UNVERIFIED">Não verificados</option>
            </select>
          </label>
          <label className="report-filter-field">
            <span>Período</span>
            <select value={historyPeriod} onChange={(event) => setHistoryPeriod(event.target.value)} aria-label="Filtrar histórico por período">
              <option value="all">Todo o histórico</option>
              <option value="24h">Últimas 24 horas</option>
              <option value="7d">Últimos 7 dias</option>
              <option value="30d">Últimos 30 dias</option>
            </select>
          </label>
          <label className="report-filter-field">
            <span>Run exibido</span>
            <select value={selectedRunId || ""} onChange={(event) => setSelectedRunId(event.target.value || undefined)} aria-label="Selecionar run exibido">
              <option value="">Último run</option>
              {report.history.map((entry) => <option key={entry.runId} value={entry.runId}>{entry.runId}</option>)}
            </select>
          </label>
        </div>
        <div className="report-history-heading">
          <div><span className="eyebrow">Histórico local</span><h2 id="report-history-title">Runs recentes</h2></div>
          <span>{visibleHistory.length} de {report.history.length} run(s)</span>
        </div>
        {visibleHistory.length === 0
          ? <p className="report-empty-inline">Nenhum run corresponde aos filtros atuais.</p>
          : <div className="report-history-list">{visibleHistory.map((entry) => (
            <button
              className={"report-history-item" + (entry.runId === report.runId ? " active" : "")}
              type="button"
              key={entry.runId}
              aria-pressed={entry.runId === report.runId}
              onClick={() => setSelectedRunId(entry.runId)}
            >
              <span className={"report-task-status report-task-status-" + outcomeTone(entry.status)} aria-hidden="true"><Glyph name={outcomeTone(entry.status) === "success" ? "check" : outcomeTone(entry.status) === "danger" ? "attention" : "activity"} size={14} /></span>
              <span className="report-history-copy"><strong>{entry.runId}</strong><small>{outcomeLabel(entry.status)} · {dateTime(entry.recordedAtUnix)}</small></span>
              <span className="report-history-meta"><b>{entry.taskCount === null ? "—" : number(entry.taskCount)} tarefa(s)</b><small>{duration(entry.wallMs)}</small></span>
            </button>
          ))}</div>}
      </section>

      <section className="report-metrics" aria-label="Resumo do relatório">
        <Metric label="Tarefas" value={number(consolidated.taskCount)} detail={report.tasks.length ? report.tasks.map((task) => outcomeLabel(task.outcome)).join(" · ") : "nenhuma tarefa registrada"} />
        <Metric label="Duração" value={duration(consolidated.wallMsRun ?? report.wallMs)} detail={consolidated.wallMsTasksSum === null ? "soma por tarefa indisponível" : "soma das tarefas " + duration(consolidated.wallMsTasksSum)} />
        <Metric
          label="Tokens"
          value={number(consolidated.tokensTotalSum)}
          detail={
            aggregateMetric("cache lido", consolidated.tokensCacheReadSum, consolidated.tokensCacheReadRollup)
            + " · "
            + aggregateMetric("cache escrito", consolidated.tokensCacheWriteSum, consolidated.tokensCacheWriteRollup)
            + " · "
            + aggregateMetric("raciocínio", consolidated.tokensReasoningSum, consolidated.tokensReasoningRollup)
          }
        />
        <Metric label="Custo" value={cost(consolidated.costMicrousdSum)} detail={costLabel(consolidated)} tone={consolidated.costMicrousdSum === null ? "muted" : ""} />
      </section>

      <section className={"panel report-coverage report-coverage-" + report.coverage.status} aria-live="polite">
        <div><span className="eyebrow">Cobertura e proveniência</span><h2>{coverageLabel(report.coverage.status)}</h2><p>{report.coverage.missing.length ? "Ausente neste recorte: " + report.coverage.missing.join(" · ") + "." : "Os campos retornados possuem recibo local."}</p></div>
        <div className="report-coverage-side"><strong>{report.operators.length ? report.operators.join(" · ") : "operadores não informados"}</strong><span>{report.unverifiedFields.length ? report.unverifiedFields.length + " campo(s) não verificado(s)" : "sem campos pendentes"}</span></div>
      </section>

      <section className="panel reports-task-panel" aria-labelledby="reports-tasks-title">
        <header className="reports-task-heading"><div><span className="eyebrow">Detalhamento</span><h2 id="reports-tasks-title">Tarefas deste run</h2></div><span>{visibleTasks.length} de {report.tasks.length} item(ns)</span></header>
        {visibleTasks.length === 0
          ? <p className="report-empty-inline">{report.tasks.length === 0 ? "O run ainda não registrou tarefas. O Runtime não cria uma linha sintética para preencher métricas ausentes." : "Nenhuma tarefa corresponde ao filtro atual."}</p>
          : <div className="reports-task-list">{visibleTasks.map((task) => (
            <details className="report-task" key={task.taskId}>
              <summary>
                <span className={"report-task-status report-task-status-" + outcomeTone(task.outcome)} aria-hidden="true"><Glyph name={outcomeTone(task.outcome) === "success" ? "check" : outcomeTone(task.outcome) === "danger" ? "attention" : "activity"} size={15} /></span>
                <span className="report-task-summary"><strong>{task.title}</strong><small>{task.issue || task.taskId} · {coverageLabel(task.coverage.status)}</small></span>
                <span className="report-task-summary-meta"><b>{number(task.tokens.total)}</b><small>{duration(task.wallMs)}</small></span>
                <Glyph name="chevron" size={17} />
              </summary>
              <TaskDetails task={task} />
            </details>
          ))}</div>}
      </section>

      <footer className="report-proof-note">
        <Glyph name="lock" size={15} />
        <span>Dados locais. A tela não solicita prompts, respostas ou credenciais; campos sem proveniência permanecem indisponíveis. Cache, raciocínio, custo e economia não são somados quando a semântica ou a proveniência está ausente.</span>
      </footer>
    </div>
  );
}
