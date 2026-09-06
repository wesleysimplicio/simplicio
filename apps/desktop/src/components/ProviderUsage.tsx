import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import "./provider_usage.css";

type WindowUsage = { usedPercent: number; windowDurationMins: number; resetsAt: number };
type GrokQuota = { status: "available" | "unavailable"; reason?: string; windows: WindowUsage[] };
type Quotas = { grok?: GrokQuota; status: "available" | "unavailable" | "busy"; observedAt?: number; groups: Array<{ id: string; windows: WindowUsage[] }> };
export function parseQuotas(value: unknown): Quotas {
  const data = value as Quotas & { schema?: string };
  if (!data || data.schema !== "simplicio.provider-quotas/v1" || !["available","unavailable","busy"].includes(data.status) || !Array.isArray(data.groups) || data.groups.length > 16) throw new Error("quota_invalid");
  for (const group of data.groups) {
    if (!group || typeof group.id !== "string" || !Array.isArray(group.windows) || group.windows.length > 2) throw new Error("quota_invalid");
    for (const w of group.windows) if (!w || !Number.isFinite(w.usedPercent) || w.usedPercent < 0 || w.usedPercent > 100 || !Number.isSafeInteger(w.windowDurationMins) || w.windowDurationMins <= 0 || !Number.isSafeInteger(w.resetsAt) || w.resetsAt < 0) throw new Error("quota_invalid");
  }
  let grok: GrokQuota | undefined;
  if (data.grok) {
    const projected = parseQuotas({schema: "simplicio.provider-quotas/v1", status: data.grok.status, groups: [{id: "grok", windows: data.grok.windows}]});
    if (projected.status === "busy") throw new Error("quota_invalid");
    grok = {status: projected.status, windows: projected.groups[0].windows, reason: typeof data.grok.reason === "string" ? data.grok.reason : undefined};
  }
  return { grok, status: data.status, observedAt: typeof data.observedAt === "number" ? data.observedAt : undefined, groups: data.groups };
}
export async function readProviderQuotas(): Promise<Quotas> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return parseQuotas(await Promise.race([invoke("desktop_provider_quotas"), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("quota_timeout")), 40_000); })]));
  } finally { clearTimeout(timer); }
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
    lock.current = true; setBusy(true);
    try {
      const next = await readProviderQuotas();
      if (alive.current) { setData(next); setError(false); }
    } catch { if (alive.current) setError(true); }
    finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  useEffect(() => {
    alive.current = true; void refresh();
    const timer = setInterval(() => { if (!document.hidden) void refresh(); }, 60_000);
    return () => { alive.current = false; clearInterval(timer); };
  }, []);
  useEffect(() => {
    if (!open) return;
    const outside = (e: PointerEvent) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", key);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", key); };
  }, [open]);
  const windows = data?.groups.flatMap(g => g.windows) ?? [];
  const summary = windows.find(w => w.windowDurationMins === 10080) ?? windows[0];
  return <div className="provider-usage" ref={root}>
    <button type="button" aria-expanded={open} aria-controls="provider-usage-panel" onClick={() => setOpen(!open)}>{summary && !error ? "Codex " + summary.usedPercent + "% usado" : busy ? "Consultando cotas…" : "Cotas dos agentes"}</button>
    {open && <section id="provider-usage-panel" className="provider-usage-panel" aria-label="Cotas dos agentes">
      <header><strong>Uso das contas</strong><button type="button" disabled={busy} onClick={() => void refresh()}>{busy ? "Consultando…" : "Atualizar cotas"}</button><button type="button" aria-label="Fechar cotas" onClick={() => setOpen(false)}>×</button></header>
      <div className="quota-display-mode" role="group" aria-label="Modo de exibição das cotas">
        <button type="button" aria-pressed={!compact} onClick={() => setCompact(false)}>Detalhado</button>
        <button type="button" aria-pressed={compact} onClick={() => setCompact(true)}>Compacto</button>
      </div>
      <h3>Codex</h3>
      {error && <p role="status">Consulta falhou. Dados anteriores não são uma leitura atual.</p>}
      {!summary && <p>{busy ? "Consultando o cliente Codex…" : "Cota não disponível. Verifique o login no cliente Codex."}</p>}
      {data?.groups.map(group => <div key={group.id}>{data.groups.length > 1 && <strong>{group.id}</strong>}{group.windows.map(w => <div className={"quota-window" + (compact ? " quota-window-compact" : "")} key={w.windowDurationMins}>
        <span>{w.windowDurationMins === 10080 ? "Semanal" : w.windowDurationMins === 300 ? "5 horas" : w.windowDurationMins + " min"} · {w.usedPercent}% usado</span>
        <progress max={100} value={w.usedPercent} aria-label={"Uso da janela de " + w.windowDurationMins + " minutos"} />
        {!compact && <small>Renova em {new Date(w.resetsAt * 1000).toLocaleString("pt-BR")}</small>}
      </div>)}</div>)}
      {data?.observedAt && <small>Fonte: Codex app-server · consulta {new Date(data.observedAt * 1000).toLocaleTimeString("pt-BR")}</small>}
      <h3>Grok</h3>
      {data?.grok?.windows.map(w => <div className={"quota-window" + (compact ? " quota-window-compact" : "")} key={w.windowDurationMins}>
        <span>{w.windowDurationMins === 10080 ? "Semanal" : w.windowDurationMins + " min"} · {w.usedPercent}% usado</span>
        <progress max={100} value={w.usedPercent} aria-label="Uso da conta Grok" />
        {!compact && <small>Renova em {new Date(w.resetsAt * 1000).toLocaleString("pt-BR")}</small>}
      </div>)}
      {!data?.grok?.windows.length && <p>{data?.grok?.reason === "refresh_in_grok" ? "Abra o Grok neste computador para renovar a sessão e consulte novamente." : data?.grok?.reason === "login_required" ? "Entre no cliente Grok neste computador para consultar sua cota." : "Cota Grok indisponível. Nenhum percentual presumido."}</p>}
      {data?.grok?.windows.length ? <small>Fonte: Grok CLI billing</small> : null}
      <button type="button" onClick={() => { setOpen(false); onHistory(); }}>Histórico de uso do Runtime</button>
      <button type="button" onClick={() => { setOpen(false); onAccounts(); }}>Contas de IA</button>
      <p className="quota-note">Cotas de assinatura não são tokens faturados nem economia do Runtime. Atualizações respeitam cache de 30 segundos.</p>
    </section>}
  </div>;
}
