import { useEffect, useRef, useState } from "react";
import { planDesktopIntegrations } from "../bridge";
import {
  hostPluginOutcomeLabel,
  integrationChangeLabel,
  type DesktopHostPlugins,
  type HostPluginOperationResult,
  type IntegrationPlan,
} from "../integration_setup";
import type { InstallFailureRecovery } from "../install_failures";

export function IntegrationSetup({ busy, onApply, onReconcile, recovery, status, initialResult, onDiagnostics }: {
  busy: boolean;
  onApply: (digest: string) => Promise<HostPluginOperationResult>;
  onReconcile: (receiptId: string) => Promise<HostPluginOperationResult>;
  recovery?: InstallFailureRecovery;
  status?: DesktopHostPlugins;
  initialResult?: HostPluginOperationResult;
  onDiagnostics?: () => void;
}) {
  const [plan, setPlan] = useState<IntegrationPlan | null>(null);
  const [result, setResult] = useState<HostPluginOperationResult | null>(initialResult ?? null);
  const [loading, setLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const loadingLock = useRef(false);
  const submittedPlanDigest = useRef<string | null>(null);
  const submittedReconcileId = useRef<string | null>(null);
  const receiptId = (result && ["partial", "requires_reconcile"].includes(result.snapshot.state) ? result.snapshot.receiptId : null)
    ?? (!result && status?.reconcileRequired ? status.reconcileReceiptId ?? null : null);
  const runtimePending = !result && status?.reconcileRequired === true;
  const blocked = Boolean((recovery && recovery !== "review" || runtimePending) && !receiptId);
  const reconcileConsumed = Boolean(receiptId && submittedReconcileId.current === receiptId);

  useEffect(() => {
    setResult(initialResult ?? null);
  }, [initialResult]);

  async function preview() {
    if (loadingLock.current || busy || blocked || runtimePending) return;
    loadingLock.current = true;
    submittedPlanDigest.current = null;
    submittedReconcileId.current = null;
    setLoading(true); setPlan(null); setResult(null); setConfirmed(false); setMessage(null);
    try { setPlan(await planDesktopIntegrations()); }
    catch { setMessage("Não foi possível preparar o plano dos oito hosts. Nenhuma configuração foi alterada."); }
    finally { setLoading(false); loadingLock.current = false; }
  }

  async function apply() {
    if (!plan || !confirmed || busy || loadingLock.current || blocked || submittedPlanDigest.current === plan.planDigest) return;
    loadingLock.current = true;
    submittedPlanDigest.current = plan.planDigest;
    setMessage(null);
    try {
      const next = await onApply(plan.planDigest);
      setResult(next);
      setMessage(hostPluginOutcomeLabel(next.snapshot));
    } catch {
      setMessage("O Runtime não devolveu um recibo canônico. Consulte o estado antes de outra aplicação.");
    } finally {
      setPlan(null); setConfirmed(false); loadingLock.current = false;
    }
  }

  async function reconcile() {
    if (!receiptId || busy || loadingLock.current || submittedReconcileId.current === receiptId) return;
    loadingLock.current = true;
    submittedReconcileId.current = receiptId;
    setMessage(null);
    try {
      const next = await onReconcile(receiptId);
      setResult(next);
      setMessage(hostPluginOutcomeLabel(next.snapshot));
    } catch {
      setMessage("A reconciliação não devolveu um recibo canônico. Nenhuma nova aplicação foi iniciada.");
    } finally {
      loadingLock.current = false;
    }
  }

  return <section className="panel integration-setup" aria-label="Configuração do MCP">
    <div><span className="eyebrow">Instalação guiada</span><h2>Configurar plugins suportados</h2>
      <p>O Runtime planeja os oito hosts com superfície nativa ou plugin. Clientes MCP e integrações guiadas continuam visíveis no inventário, sem serem tratados como plugins instaláveis.</p></div>
    <button type="button" className="button button-secondary" disabled={busy || loading || blocked} onClick={() => void preview()}>{loading ? "Preparando plano…" : "Revisar configuração MCP"}</button>
    {(blocked || runtimePending) && <div className="integration-recovery"><p>O Runtime precisa esclarecer uma operação anterior. Atualizar a tela não verifica, reconcilia nem repete a aplicação.</p>{receiptId && !reconcileConsumed
      ? <button type="button" className="button button-primary" disabled={busy} onClick={() => void reconcile()}>Reconciliar recibo</button>
      : onDiagnostics && <button type="button" className="button button-secondary" disabled={busy} onClick={onDiagnostics}>Abrir diagnóstico</button>}</div>}
    {plan && !blocked && <div className="integration-plan">
      <p>{plan.source === "preview" ? "Demonstração: nenhuma alteração real." : "Plano do Runtime, ainda não executado."} {plan.hosts.length} hosts revisáveis.</p>
      <ul>{plan.hosts.map((host) => <li key={host.host}><span>{host.host}</span><strong>{integrationChangeLabel(host)}</strong></li>)}</ul>
      <label className="setup-consent"><input type="checkbox" checked={confirmed} disabled={busy} onChange={(event) => setConfirmed(event.target.checked)} />Autorizo o Runtime a aplicar exatamente este plano identificado por digest.</label>
      <div className="settings-actions"><button type="button" className="button button-primary" disabled={!confirmed || busy} onClick={() => void apply()}>{busy ? "Configurando…" : "Aplicar configuração MCP"}</button><button type="button" className="button button-secondary" disabled={busy} onClick={() => { setPlan(null); setConfirmed(false); }}>Cancelar</button></div>
    </div>}
    {result && <div className="integration-plan" role="region" aria-label="Resultado dos plugins"><p>{hostPluginOutcomeLabel(result.snapshot)}</p>
      <ul>{result.snapshot.hosts.map((host) => <li key={host.host}><span>{host.host}</span><strong>{host.status === "applied_unverified" ? "Aplicado; não verificado" : host.status}</strong></li>)}</ul>
      {receiptId && !reconcileConsumed && <button type="button" className="button button-primary" disabled={busy} onClick={() => void reconcile()}>Reconciliar recibo</button>}
      {receiptId && reconcileConsumed && onDiagnostics && <button type="button" className="button button-secondary" disabled={busy} onClick={onDiagnostics}>Consultar estado no diagnóstico</button>}
    </div>}
    {!result && status && status.hosts.length > 0 && <div className="integration-plan" role="region" aria-label="Estado dos plugins"><p>Último estado canônico do Runtime.</p>
      <ul>{status.hosts.map((host) => <li key={host.host}><span>{host.host}</span><strong>{host.status === "applied_unverified" ? "Aplicado; não verificado" : host.status}</strong></li>)}</ul>
    </div>}
    {message && <p role="status">{message}</p>}
  </section>;
}
