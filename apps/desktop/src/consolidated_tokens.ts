import { parseTokenUsageReport, type TokenTotals } from "./token_usage";

export const CONSOLIDATED_PERIODS = [["7d", "7 dias"], ["30d", "30 dias"], ["3m", "3 meses"], ["6m", "6 meses"], ["12m", "12 meses"]] as const;
export type ConsolidatedPeriod = typeof CONSOLIDATED_PERIODS[number][0];
export interface ConsolidatedQuery { repoPaths: string[]; fromEpoch: number; toEpoch: number; timezoneOffsetSeconds: number }
export type ProjectReportStatus = "ready" | "missing" | "invalid" | "timeout" | "skipped" | "duplicate";
export interface ConsolidatedProject { id: string; path: string; name: string; status: ProjectReportStatus; totals: TokenTotals | null; reportHash: string | null }
export interface ConsolidatedReport extends Omit<ConsolidatedQuery, "repoPaths"> {
  schema: "simplicio.desktop-consolidated-tokens/v1"; source: "runtime"; generatedAtEpoch: number;
  projects: ConsolidatedProject[]; totals: TokenTotals | null; reportHash: string;
}
export const PROJECT_STATUS: Record<ProjectReportStatus, string> = { ready: "Consultado", missing: "Sem ledger de uso", invalid: "Não validado", timeout: "Sem resposta", skipped: "Não consultado (limite)", duplicate: "Ledger já contabilizado" };
const hashPattern = /^sha256:[a-f0-9]{64}$/;
const absolutePath = /^(?:\/(?!\/)|[a-zA-Z]:[\\/])/;
const validPath = (value: unknown): value is string => typeof value === "string" && value.length <= 4096 && absolutePath.test(value) && !/[\u0000-\u001f\u007f]/.test(value);
function invalid(): never { throw new Error("consolidated_report_invalid"); }
function object(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : invalid(); }
function epoch(value: unknown): number { return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && value <= 8_640_000_000_000 ? value : invalid(); }

/** Rolling days; calendar months clamp the day at month-end, in local time. */
export function consolidatedRange(period: ConsolidatedPeriod, now = new Date()): Omit<ConsolidatedQuery, "repoPaths"> {
  const end = new Date(now);
  const start = new Date(now);
  if (period === "7d" || period === "30d") start.setTime(end.getTime() - (period === "7d" ? 7 : 30) * 86_400_000);
  else {
    const day = start.getDate();
    start.setDate(1);
    start.setMonth(start.getMonth() - Number.parseInt(period, 10));
    const lastDay = new Date(start.getFullYear(), start.getMonth() + 1, 0).getDate();
    start.setDate(Math.min(day, lastDay));
  }
  const fromEpoch = Math.floor(start.getTime() / 1000), toEpoch = Math.floor(end.getTime() / 1000);
  if (!Number.isSafeInteger(fromEpoch) || fromEpoch < 0 || fromEpoch >= toEpoch) throw new Error("token_query_invalid");
  return { fromEpoch, toEpoch, timezoneOffsetSeconds: -end.getTimezoneOffset() * 60 };
}

export function collectReportPaths(paths: string[]): { paths: string[]; omitted: number } {
  const unique = [...new Set(paths.filter(validPath))].sort();
  return { paths: unique.slice(0, 96), omitted: unique.length - Math.min(unique.length, 96) };
}

/** Validate provenance, exact requested scope and the native checked sum. */
export function parseConsolidatedReport(value: unknown, query: ConsolidatedQuery): ConsolidatedReport {
  const raw = object(value);
  if (raw.schema !== "simplicio.desktop-consolidated-tokens/v1" || raw.source !== "runtime"
    || raw.fromEpoch !== query.fromEpoch || raw.toEpoch !== query.toEpoch || raw.timezoneOffsetSeconds !== query.timezoneOffsetSeconds
    || !hashPattern.test(String(raw.reportHash)) || !Array.isArray(raw.projects) || raw.projects.length !== query.repoPaths.length || raw.projects.length > 96) invalid();
  const fromEpoch = epoch(raw.fromEpoch), toEpoch = epoch(raw.toEpoch);
  if (fromEpoch >= toEpoch) invalid();
  const totals = (input: unknown): TokenTotals => {
    try { return parseTokenUsageReport({ schema: "workspace.token-analytics-report/v1", generated_by: "sqlite_ledger", report_hash: raw.reportHash,
      now_epoch: epoch(raw.generatedAtEpoch), session_id: null, timezone_offset_seconds: query.timezoneOffsetSeconds,
      periods: [{ window: "custom", from_epoch: fromEpoch, to_epoch: toEpoch, totals: input }] }).periods[0].totals; } catch { return invalid(); }
  };
  const seen = new Set<string>();
  const projects = raw.projects.map((item): ConsolidatedProject => {
    const p = object(item);
    if (typeof p.id !== "string" || p.id.length < 1 || p.id.length > 256 || !validPath(p.path)
      || !query.repoPaths.includes(p.path) || seen.has(p.path) || typeof p.name !== "string" || !p.name || p.name.length > 4096
      || !Object.hasOwn(PROJECT_STATUS, String(p.status))) invalid();
    seen.add(p.path);
    const ready = p.status === "ready";
    if (ready ? !hashPattern.test(String(p.reportHash)) : p.totals !== null || p.reportHash !== null) invalid();
    return { id: p.id, path: p.path, name: p.name, status: p.status as ProjectReportStatus, totals: ready ? totals(p.totals) : null, reportHash: ready ? String(p.reportHash) : null };
  });
  const ready = projects.filter(p => p.totals !== null);
  const sum = raw.totals === null ? null : totals(raw.totals);
  if (Boolean(ready.length) !== Boolean(sum)) invalid();
  if (sum) for (const key of Object.keys(sum) as Array<keyof TokenTotals>) {
    const expected = ready.reduce((n, p) => n + p.totals![key], 0);
    if (!Number.isSafeInteger(expected) || sum[key] !== expected) invalid();
  }
  return { schema: "simplicio.desktop-consolidated-tokens/v1", source: "runtime", fromEpoch, toEpoch,
    timezoneOffsetSeconds: query.timezoneOffsetSeconds, generatedAtEpoch: epoch(raw.generatedAtEpoch), projects, totals: sum, reportHash: String(raw.reportHash) };
}

export function consolidatedError(cause: unknown): string {
  const code = cause instanceof Error ? cause.message : String(cause);
  if (code.includes("preview_no_runtime")) return "Abra o app desktop para consolidar os ledgers locais. A demonstração não inventa dados de uso.";
  if (code.includes("busy") || code.includes("timeout")) return "A consulta ainda não foi concluída. Aguarde antes de atualizar; nenhum total foi presumido.";
  if (code.includes("access")) return "O acesso da conta não foi confirmado para esta consulta. Verifique a conta e tente novamente.";
  return "Não foi possível validar o consolidado. Atualize para consultar novamente; nenhum consumo foi presumido.";
}

/** One batch at a time. Retain its slot after observer timeout until native completion. */
export function createConsolidatedReader(invoke: (request: ConsolidatedQuery) => Promise<unknown>, timeoutMs = 130_000) {
  let pending: { key: string; promise: Promise<ConsolidatedReport> } | undefined;
  return (request: ConsolidatedQuery): Promise<ConsolidatedReport> => {
    const key = JSON.stringify(request);
    if (pending) return pending.key === key ? pending.promise : Promise.reject(new Error("consolidated_report_busy"));
    const native = Promise.resolve().then(() => invoke(request));
    const promise = new Promise<ConsolidatedReport>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("consolidated_report_timeout")), timeoutMs);
      native.then(value => {
        clearTimeout(timer); pending = undefined;
        try { resolve(parseConsolidatedReport(value, request)); } catch (cause) { reject(cause); }
      }, cause => { clearTimeout(timer); pending = undefined; reject(cause); });
    });
    pending = { key, promise };
    return promise;
  };
}
