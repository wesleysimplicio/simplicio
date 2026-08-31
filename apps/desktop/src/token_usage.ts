/** The Runtime owns aggregation. The Desktop only validates and presents its report. */
export const TOKEN_PERIODS = [
  ["today", "Hoje"], ["7d", "7 dias"], ["1m", "1 mês"],
  ["3m", "3 meses"], ["6m", "6 meses"], ["12m", "12 meses"],
  ["custom", "Personalizado"],
] as const;

export type TokenPeriod = (typeof TOKEN_PERIODS)[number][0];

export interface TokenQuery {
  repoPath?: string;
  sessionId?: string;
  fromEpoch?: number;
  toEpoch?: number;
  timezoneOffsetSeconds: number;
}

export interface TokenTotals {
  sample_count: number;
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  paid_remote_tokens: number;
  total_tokens: number;
  missing_usage_events: number;
  receipt_count: number;
}

export interface TokenUsageReport {
  schema: "workspace.token-analytics-report/v1";
  now_epoch: number;
  session_id: string | null;
  timezone_offset_seconds: number;
  periods: Array<{ window: TokenPeriod; from_epoch: number; to_epoch: number; totals: TokenTotals }>;
  generated_by: "sqlite_ledger";
  report_hash: string;
}

const totalKeys: ReadonlyArray<keyof TokenTotals> = [
  "sample_count", "input_tokens", "cached_input_tokens", "output_tokens",
  "reasoning_tokens", "paid_remote_tokens", "total_tokens", "missing_usage_events", "receipt_count",
];

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("token_report_invalid");
  return value as Record<string, unknown>;
}

function integer(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) throw new Error("token_report_invalid");
  return value;
}

/** Reject malformed IPC responses and omit unknown fields, raw samples and paths. */
export function parseTokenUsageReport(value: unknown): TokenUsageReport {
  const report = object(value);
  if (report.schema !== "workspace.token-analytics-report/v1" || report.generated_by !== "sqlite_ledger"
    || typeof report.report_hash !== "string" || !/^sha256:[a-f0-9]{64}$/.test(report.report_hash)
    || !Array.isArray(report.periods) || report.periods.length === 0 || report.periods.length > 7
    || !(report.session_id === null || (typeof report.session_id === "string" && report.session_id.length <= 256))
    || typeof report.timezone_offset_seconds !== "number" || !Number.isInteger(report.timezone_offset_seconds)
    || Math.abs(report.timezone_offset_seconds) > 86_400) throw new Error("token_report_invalid");
  const seen = new Set<string>();
  const periods = report.periods.map((raw) => {
    const period = object(raw);
    if (typeof period.window !== "string" || !TOKEN_PERIODS.some(([id]) => id === period.window)
      || seen.has(period.window)) throw new Error("token_report_invalid");
    seen.add(period.window);
    const from = integer(period.from_epoch);
    const to = integer(period.to_epoch);
    if (from >= to) throw new Error("token_report_invalid");
    const rawTotals = object(period.totals);
    const totals = Object.fromEntries(totalKeys.map((key) => [key, integer(rawTotals[key])])) as unknown as TokenTotals;
    if (totals.cached_input_tokens > totals.input_tokens || totals.missing_usage_events > totals.sample_count
      || totals.receipt_count > totals.sample_count
      || totals.total_tokens !== totals.input_tokens + totals.output_tokens + totals.reasoning_tokens) {
      throw new Error("token_report_invalid");
    }
    return { window: period.window as TokenPeriod, from_epoch: from, to_epoch: to, totals };
  });
  return {
    schema: "workspace.token-analytics-report/v1", now_epoch: integer(report.now_epoch),
    session_id: report.session_id, timezone_offset_seconds: report.timezone_offset_seconds,
    periods, generated_by: "sqlite_ledger", report_hash: report.report_hash,
  };
}

export function parseTokenExportReceipt(value: unknown): { format: "json" | "csv"; path: string; bytes: number } {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("token_export_unconfirmed");
  const receipt = value as Record<string, unknown>;
  if (receipt.schema !== "simplicio.desktop-token-export/v1" || !["json", "csv"].includes(String(receipt.format))
    || typeof receipt.path !== "string" || !receipt.path || receipt.path.length > 4096 || receipt.path.includes("\0")
    || typeof receipt.bytes !== "number" || !Number.isSafeInteger(receipt.bytes) || receipt.bytes < 1
    || receipt.bytes > 65_536) throw new Error("token_export_unconfirmed");
  return { format: receipt.format as "json" | "csv", path: receipt.path, bytes: receipt.bytes };
}

export function tokenExportErrorMessage(error: unknown): string {
  const reason = error instanceof Error ? error.message : String(error);
  if (reason.includes("token_export_report_expired")) return "O relatório saiu do cache local. Consulte o uso novamente antes de exportar.";
  if (reason.includes("token_export_permission_denied")) return "O sistema não permitiu salvar em Downloads. Confira as permissões do app; nenhuma permissão foi alterada.";
  if (reason.includes("token_export_downloads_unavailable")) return "A pasta Downloads não está disponível. Restaure a pasta e tente novamente.";
  if (reason.includes("token_export_names_exhausted")) return "Há muitas exportações com esse nome em Downloads. Organize os arquivos antes de tentar novamente.";
  if (reason.includes("desktop_access_not_active")) return "A sessão ou assinatura não está ativa no Runtime. Verifique sua conta antes de exportar.";
  return "Não foi possível confirmar a exportação. Verifique Downloads e o espaço em disco antes de tentar novamente.";
}

export function tokenErrorMessage(error: unknown): string {
  const reason = error instanceof Error ? error.message : String(error);
  if (reason === "desktop_access_unverified") return "O Runtime não confirmou o acesso da conta nesta consulta. Verifique a conta e tente novamente; nenhuma assinatura foi considerada inativa.";
  if (reason.includes("token_ledger_unavailable")) return "Nenhum ledger de uso encontrado nesta pasta. Selecione o projeto que recebeu os eventos do Runtime; ausência de telemetria não significa consumo zero.";
  if (reason.includes("preview_no_runtime")) return "A demonstração não consulta seu uso. Abra o app instalado para ler os recibos do Runtime.";
  if (reason.includes("token_query_invalid")) return "Confira a pasta absoluta, a sessão e as datas. O início deve ser anterior ao fim.";
  if (reason.includes("token_report_invalid")) return "O Runtime retornou um relatório incompatível. Nenhum total foi exibido.";
  return "Não foi possível consultar o relatório no Runtime. Nenhum consumo foi presumido.";
}
