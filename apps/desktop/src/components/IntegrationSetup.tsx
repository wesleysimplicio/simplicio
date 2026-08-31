import { useRef, useState } from "react";
import { planDesktopIntegrations } from "../bridge";
import { integrationChangeLabel, type IntegrationPlan } from "../integration_setup";
import type { InstallFailureRecovery } from "../install_failures";

export function IntegrationSetup({ busy, onApply, recovery, onDiagnostics }: {
  busy: boolean; onApply: (digest: string) => Promise<boolean>; recovery?: InstallFailureRecovery; onDiagnostics?: () => void;
}) {
  const [plan, setPlan] = useState<IntegrationPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const loadingLock = useRef(false);
  const blocked = Boolean(recovery && recovery !== "review");

  async function preview() {
    if (loadingLock.current || busy || blocked) return;
    loadingLock.current = true;
    setLoading(true); setPlan(null); setConfirmed(false); setMessage(null);
    try { setPlan(await planDesktopIntegrations()); }
    catch { setMessage("Não foi possível preparar o plano. Nenhuma configuração foi alterada."); }
    finally { setLoading(false); loadingLock.current = false; }
  }

  async function apply() {
    if (!plan || !confirmed || busy || loadingLock.current || blocked) return;
    loadingLock.current = true;
    try {
      const ok = await onApply(plan.planDigest);
      setMessage(ok ? "Configuração concluída pelo Runtime. Abra uma nova sessão nos clientes para confirmar a conexão MCP." : "O resultado da configuração precisa ser esclarecido. Não repita a aplicação enquanto houver uma tentativa pendente ou incerta.");
    } finally {
      setPlan(null); setConfirmed(false); loadingLock.current = false;
    }
  }

  return <section className="panel integration-setup" aria-label="Configuração do MCP">
    <div><span className="eyebrow">Instalação guiada</span><h2>Configurar o Simplicio nos seus apps</h2>
      <p>O app inclui o Runtime. Após sua confirmação, ele copia o binário para a instalação gerenciada e registra MCP e hooks nos clientes detectados, com backups. Este fluxo não altera o PATH nem inicia um serviço global; plugins de marketplace e autorizações continuam sob controle de cada host.</p></div>
    <button type="button" className="button button-secondary" disabled={busy || loading || blocked} onClick={() => void preview()}>{loading ? "Preparando plano…" : "Revisar configuração MCP"}</button>
    {blocked && <div className="integration-recovery"><p>{recovery === "refresh" ? "A aplicação foi confirmada; falta verificar o estado final. Consulte o diagnóstico, sem reinstalar." : recovery === "wait" ? "Já há uma instalação em andamento. Aguarde sua conclusão antes de outra aplicação." : "Há uma instalação com resultado incerto. Novas aplicações estão bloqueadas nesta sessão; atualizar ou reiniciar o app não comprova a conclusão."}</p>{onDiagnostics && <button type="button" className="button button-secondary" disabled={busy} onClick={onDiagnostics}>Atualizar diagnóstico</button>}</div>}
    {plan && !blocked && <div className="integration-plan">
      <p>{plan.source === "preview" ? "Demonstração: nenhuma alteração real." : "Plano do Runtime, ainda não executado."} {plan.changes.filter((row) => row.changed).length} alterações propostas.</p>
      <ul>{plan.changes.map((row) => <li key={row.label}><span>{row.label}</span><strong>{integrationChangeLabel(row)}</strong></li>)}</ul>
      <label className="setup-consent"><input type="checkbox" checked={confirmed} disabled={busy} onChange={(event) => setConfirmed(event.target.checked)} />Autorizo o Runtime a aplicar este plano de instalação e registro.</label>
      <div className="settings-actions"><button type="button" className="button button-primary" disabled={!confirmed || busy} onClick={() => void apply()}>{busy ? "Configurando…" : "Aplicar configuração MCP"}</button><button type="button" className="button button-secondary" disabled={busy} onClick={() => { setPlan(null); setConfirmed(false); }}>Cancelar</button></div>
    </div>}
    {message && <p role="status">{message}</p>}
  </section>;
}
