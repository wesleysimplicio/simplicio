import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import "./provider_usage.css";

type WindowUsage = { usedPercent: number; windowDurationMins: number; resetsAt: number };
type ProviderQuota = {
  id: "codex" | "grok";
  source: "codex_app_server" | "grok_cli_billing";
  observedAt: number;
  accountScope: "local_authenticated_account" | "local_cli_session";
  redacted: true;
  status: "fresh" | "stale" | "unavailable";
  error?: string;
  windows: WindowUsage[];
};
type Quotas = {
  schema: "simplicio.provider-quotas/v2";
  status: "available" | "stale" | "unavailable" | "busy";
  observedAt: number;
  providers: ProviderQuota[];
};

const providerIds = ["codex", "grok"] as const;
const sources = ["codex_app_server", "grok_cli_billing"] as const;
const scopes = ["local_authenticated_account", "local_cli_session"] as const;
const statuses = ["fresh", "stale", "unavailable"] as const;
const maxProviderWindows = 32;
const maxWindowDurationMins = 366 * 24 * 60;
const providerContract = {
  codex: { source: "codex_app_server", accountScope: "local_authenticated_account" },
  grok: { source: "grok_cli_billing", accountScope: "local_cli_session" },
} as const;

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseWindow(value: unknown): WindowUsage {
  if (!record(value)) throw new Error("quota_invalid");
  const used = value.usedPercent;
  const minutes = value.windowDurationMins;
  const resets = value.resetsAt;
  if (typeof used !== "number" || !Number.isFinite(used) || used < 0 || used > 100
    || typeof minutes !== "number" || !Number.isSafeInteger(minutes) || minutes <= 0 || minutes > maxWindowDurationMins
    || typeof resets !== "number" || !Number.isSafeInteger(resets) || resets < 0 || resets > Number.MAX_SAFE_INTEGER) {
    throw new Error("quota_invalid");
  }
  return { usedPercent: used, windowDurationMins: minutes, resetsAt: resets };
}

export function parseQuotas(value: unknown): Quotas {
  if (!record(value)
    || value.schema !== "simplicio.provider-quotas/v2"
    || !["available", "stale", "unavailable", "busy"].includes(String(value.status))
    || !Number.isSafeInteger(value.observedAt) || Number(value.observedAt) < 0
    || !Array.isArray(value.providers) || value.providers.length > 2) {
    throw new Error("quota_invalid");
  }
  const seen = new Set<string>();
  const providers = value.providers.map((raw): ProviderQuota => {
    const id = record(raw) ? raw.id : undefined;
    const contract = providerContract[id as keyof typeof providerContract];
    if (!record(raw)
      || !providerIds.includes(raw.id as typeof providerIds[number])
      || seen.has(String(raw.id))
      || !sources.includes(raw.source as typeof sources[number])
      || !scopes.includes(raw.accountScope as typeof scopes[number])
      || !contract || raw.source !== contract.source || raw.accountScope !== contract.accountScope
      || raw.redacted !== true
      || !Number.isSafeInteger(raw.observedAt) || Number(raw.observedAt) < 0
      || Number(raw.observedAt) > Number(value.observedAt)
      || !statuses.includes(raw.status as typeof statuses[number])
      || !Array.isArray(raw.windows) || raw.windows.length > maxProviderWindows
      || (raw.status === "unavailable" && raw.windows.length !== 0)
      || (raw.status !== "unavailable" && raw.windows.length === 0)) {
      throw new Error("quota_invalid");
    }
    seen.add(String(raw.id));
    const windows = raw.windows.map(parseWindow);
    const error = raw.error === undefined
      ? undefined
      : typeof raw.error === "string" && /^[a-z_]{1,64}$/.test(raw.error) ? raw.error : null;
    if (error === null) throw new Error("quota_invalid");
    return {
      id: raw.id as ProviderQuota["id"],
      source: raw.source as ProviderQuota["source"],
      observedAt: raw.observedAt as number,
      accountScope: raw.accountScope as ProviderQuota["accountScope"],
      redacted: true,
      status: raw.status as ProviderQuota["status"],
      error,
      windows,
    };
  });
  if (value.status === "busy" && providers.length !== 0) throw new Error("quota_invalid");
  if (value.status !== "busy") {
    const expectedStatus = providers.some(provider => provider.status === "fresh")
      ? "available"
      : providers.some(provider => provider.status === "stale") ? "stale" : "unavailable";
    if (value.status !== expectedStatus) throw new Error("quota_invalid");
  }
  return {
    schema: "simplicio.provider-quotas/v2",
    status: value.status as Quotas["status"],
    observedAt: value.observedAt as number,
    providers,
  };
}

export async function readProviderQuotas(): Promise<Quotas> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return parseQuotas(await Promise.race([
      invoke("desktop_provider_quotas"),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("quota_timeout")), 40_000); }),
    ]));
  } finally {
    clearTimeout(timer);
  }
}

function providerLabel(provider: ProviderQuota | undefined): string {
  if (provider?.status === "stale") return "Dados anteriores; atualize para uma leitura atual.";
  if (provider?.error === "refresh_in_grok") return "Abra o Grok neste computador para renovar a sessão e consulte novamente.";
  if (provider?.error === "login_required") return "Entre no cliente neste computador para consultar sua cota.";
  return "Cota indisponível. Nenhum percentual presumido.";
}

function sourceLabel(provider: ProviderQuota): string {
  return provider.source === "codex_app_server" ? "Codex app-server" : "Grok CLI billing";
}

export function ProviderUsage({ onAccounts, onHistory }: { onAccounts: () => void; onHistory: () => void }) {
  const [open, setOpen] = useState(false);
  const [compact, setCompact] = useState(false);
  const [data, setData] = useState<Quotas | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const lock = useRef(false);
  const alive = useRef(false);
  const root = useRef<HTMLDivElement>(null);

  async function refresh() {
    if (lock.current || !("__TAURI_INTERNALS__" in window)) return;
    lock.current = true;
    setBusy(true);
    try {
      const next = await readProviderQuotas();
      if (alive.current) { setData(next); setError(false); }
    } catch {
      if (alive.current) setError(true);
    } finally {
      lock.current = false;
      if (alive.current) setBusy(false);
    }
  }

  useEffect(() => {
    alive.current = true;
    void refresh();
    const timer = setInterval(() => { if (!document.hidden) void refresh(); }, 60_000);
    return () => { alive.current = false; clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const key = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", key); };
  }, [open]);

  const codex = data?.providers.find(provider => provider.id === "codex");
  const grok = data?.providers.find(provider => provider.id === "grok");
  const summary = codex?.windows.find(window => window.windowDurationMins === 10080) ?? codex?.windows[0];
  const renderWindows = (provider: ProviderQuota | undefined, label: string) => <>
    <h3>{label}</h3>
    {provider?.windows.map((window, index) => <div className={"quota-window" + (compact ? " quota-window-compact" : "")} key={window.windowDurationMins + "-" + window.resetsAt + "-" + index}>
      <span>{window.windowDurationMins === 10080 ? "Semanal" : window.windowDurationMins === 300 ? "5 horas" : window.windowDurationMins + " min"} · {window.usedPercent}% usado</span>
      <progress max={100} value={window.usedPercent} aria-label={"Uso da janela de " + window.windowDurationMins + " minutos"} />
      {!compact && <small>Renova em {new Date(window.resetsAt * 1000).toLocaleString("pt-BR")}</small>}
    </div>)}
    {(!provider || !provider.windows.length) && <p>{providerLabel(provider)}</p>}
    {provider && <small>Fonte: {sourceLabel(provider)} · consulta {new Date(provider.observedAt * 1000).toLocaleTimeString("pt-BR")}{provider.status === "stale" ? " · desatualizada" : ""}</small>}
  </>;

  return <div className="provider-usage" ref={root}>
    <button type="button" aria-expanded={open} aria-controls="provider-usage-panel" onClick={() => setOpen(!open)}>
      {summary && !error ? "Codex " + summary.usedPercent + "% usado" + (codex?.status === "stale" ? " · desatualizado" : "") : busy ? "Consultando cotas…" : "Cotas dos agentes"}
    </button>
    {open && <section id="provider-usage-panel" className="provider-usage-panel" aria-label="Cotas dos agentes">
      <header><strong>Uso das contas</strong><button type="button" disabled={busy} onClick={() => void refresh()}>{busy ? "Consultando…" : "Atualizar cotas"}</button><button type="button" aria-label="Fechar cotas" onClick={() => setOpen(false)}>×</button></header>
      <div className="quota-display-mode" role="group" aria-label="Modo de exibição das cotas">
        <button type="button" aria-pressed={!compact} onClick={() => setCompact(false)}>Detalhado</button>
        <button type="button" aria-pressed={compact} onClick={() => setCompact(true)}>Compacto</button>
      </div>
      {error && <p role="status">Consulta falhou. Dados anteriores não são uma leitura atual.</p>}
      {renderWindows(codex, "Codex")}
      {renderWindows(grok, "Grok")}
      <button type="button" onClick={() => { setOpen(false); onHistory(); }}>Histórico de uso do Runtime</button>
      <button type="button" onClick={() => { setOpen(false); onAccounts(); }}>Contas de IA</button>
      <p className="quota-note">Cotas de assinatura não são tokens faturados nem economia do Runtime. Atualizações respeitam cache de 30 segundos; estados desatualizados não são tratados como leituras atuais.</p>
    </section>}
  </div>;
}
