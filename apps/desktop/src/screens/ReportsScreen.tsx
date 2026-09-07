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
      return "warning";
    default:
      return "neutral";
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
  const parts = [
    tokens.total === null ? "total —" : tokens.total.toLocaleString("pt-BR") + " tokens",
    tokens.cacheRead === null ? "cache lido —" : "cache lido " + tokens.cacheRead.toLocaleString("pt-BR"),
    tokens.cacheWrite === null ? "cache escrito —" : "cache escrito " + tokens.cacheWrite.toLocaleString("pt-BR"),
    tokens.reasoning === null ? "raciocínio —" : "raciocínio " + tokens.reasoning.toLocaleString("pt-BR"),
  ];
  return parts.join(" · ");
}

function validationLabel(validation: ReportValidation): string {
  if (validation.status === "passed") return validation.checks + " verificações aprovadas";
  if (validation.status === "failed") return validation.failures + " falha(s) em " + validation.checks + " verificações";
  if (validation.status === "not_run") return "não executada";
  return "não disponível";
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
              {task.errors.map((error, index) => <li className="report-event-error" key={"error-" + error.code + index}><strong>{error.code}</strong><span>{error.message || "detalhe não disponível"}{error.retryable === true ? " · retryável" : ""}</span></li>)}
              {task.retries.map((retry) => <li className="report-event-retry" key={"retry-" + retry.attempt}><strong>Tentativa {retry.attempt}</strong><span>{retry.reasonCode} · {retry.status} · {duration(retry.wallMs)}</span></li>)}
            </ul>}
        </section>
      </div>

      <div className={"report-validation report-validation-" + outcomeTone(task.validation.status)}>
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
  const request = useRef(0);

  const refresh = useCallback(async () => {
    const current = ++request.current;
    setBusy(true);
    setError(null);
    try {
      const next = await loadDesktopExecutionReport(repoPath || undefined, selectedRunId);
      if (current === request.current) setReport(next);
    } catch (cause) {
      if (current === request.current) setError(cause instanceof Error ? cause.message : "execution_report_unavailable");
    } finally {
      if (current === request.current) setBusy(false);
    }
  }, [repoPath, selectedRunId]);

  useEffect(() => {
    void refresh();
    const native = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (!native) return undefined;
    const timer = window.setInterval(() => { void refresh(); }, 5_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  function exportReport() {
    if (report) downloadExecutionReport(report);
  }

  if (!report && busy) {
    return <div className="page secondary-page reports-page"><div className="report-loading" role="status" aria-live="polite"><span className="eyebrow">Telemetria local</span><h1>Relatórios de execução</h1><p>Consultando o último relatório do Runtime…</p><div className="report-loading-bar" /></div></div>;
  }

  if (!report) {
    return <div className="page secondary-page reports-page"><section className="page-heading"><div><span className="eyebrow">Telemetria local</span><h1>Relatórios de execução</h1><p>Resumo por tarefa com evidência de etapas, ferramentas, custo e validação.</p></div><button className="button button-secondary" type="button" onClick={() => void refresh()} disabled={busy}><Glyph name="refresh" size={16} />{busy ? "Atualizando…" : "Tentar novamente"}</button></section><p className="inline-error" role="alert">Não foi possível ler o relatório do Runtime{error ? ": " + error : "."}</p></div>;
  }

  if (!report.present) {
    return <div className="page secondary-page reports-page"><section className="page-heading"><div><span className="eyebrow">Telemetria local</span><h1>Relatórios de execução</h1><p>Resumo por tarefa com evidência de etapas, ferramentas, custo e validação.</p></div><button className="button button-secondary" type="button" onClick={() => void refresh()} disabled={busy}><Glyph name="refresh" size={16} />Atualizar</button></section><section className="panel report-empty" role="status"><div className="report-empty-mark"><Glyph name="activity" size={24} /></div><h2>Nenhum relatório registrado</h2><p>{report.message}</p><p className="report-muted">O Runtime só mostra números quando há recibo local. Dados ausentes permanecem como indisponíveis.</p></section></div>;
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
        <span>Atualizado {dateTime(report.fetchedAtUnix)} · revisão {report.revision || "não informada"}</span>
      </section>

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
            (consolidated.tokensCacheReadSum === null ? "cache lido —" : "cache lido " + number(consolidated.tokensCacheReadSum))
            + " · "
            + (consolidated.tokensCacheWriteSum === null ? "cache escrito —" : "cache escrito " + number(consolidated.tokensCacheWriteSum))
          }
        />
        <Metric label="Custo" value={cost(consolidated.costMicrousdSum)} detail={consolidated.costRollup === "complete" ? "preço confirmado" : consolidated.costRollup === "partial" ? "preço parcial" : "sem preço confirmado"} tone={consolidated.costMicrousdSum === null ? "muted" : ""} />
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
        <span>Dados locais e redigidos: prompts, respostas, credenciais e caminhos pessoais não são exibidos. Cache, raciocínio, custo e economia não são somados quando a semântica ou a proveniência está ausente.</span>
      </footer>
    </div>
  );
}
