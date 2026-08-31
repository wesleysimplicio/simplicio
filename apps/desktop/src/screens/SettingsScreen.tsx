import { useRef, useState } from "react";
import type { DesktopSnapshot } from "../contracts";
import { Glyph } from "../components/Brand";
import { exportDesktopSnapshot } from "../bridge";
import { runtimeSummary } from "../workbench";
import { formatRuntimeTimestamp } from "../runtime_timestamp";

export function redactedDiagnostic(snapshot: DesktopSnapshot) {
  return {
    schema: "simplicio.desktop-diagnostic/v1",
    generatedAt: snapshot.generatedAt,
    source: snapshot.source,
    access: { state: snapshot.access.state, plan: snapshot.access.plan, reasonCode: snapshot.access.reasonCode },
    runtime: { state: snapshot.runtime.state, version: snapshot.runtime.version, transport: snapshot.runtime.transport },
    savings: { proofKind: snapshot.savings.proofKind, ledgerStatus: snapshot.savings.ledgerStatus, eventCount: snapshot.savings.eventCount },
    providers: snapshot.providers.map(({ id, state, reasonCode }) => ({ id, state, reasonCode })),
    redaction: snapshot.redaction,
  };
}

function previewDownload(snapshot: DesktopSnapshot) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(redactedDiagnostic(snapshot), null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url; link.download = "simplicio-diagnostic.json"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function SettingsScreen({ snapshot, busy, onRefresh, onSubscribe, onLogout, logoutBusy, section = "all" }:
  { snapshot: DesktopSnapshot; busy: boolean; onRefresh: () => void; onSubscribe: () => void; onLogout: () => void; logoutBusy: boolean; section?: "account" | "diagnostics" | "all" }) {
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const exportLock = useRef(false);
  const runtime = runtimeSummary(snapshot);
  async function download() {
    if (exportLock.current) return;
    exportLock.current = true; setExporting(true); setExported(null); setExportError(null);
    try {
      const path = await exportDesktopSnapshot("diagnostic");
      if (path) setExported(path);
      else { previewDownload(snapshot); setExported("download da demonstração"); }
    } catch { setExportError("Não foi possível salvar o diagnóstico em Downloads. Verifique as permissões e o espaço em disco."); }
    finally { exportLock.current = false; setExporting(false); }
  }
  return <div className="page preferences-page account-page">
    <section className="page-heading"><div><h1>{section === "diagnostics" ? "Runtime e diagnóstico" : "Conta Simplicio"}</h1><p>{section === "diagnostics" ? "Estado local verificado pelo Runtime. Diagnósticos sem dados sensíveis." : "Sua identidade e assinatura, verificadas pelo Simplicio Runtime."}</p></div></section>
    {section !== "diagnostics" && <section className="settings-section"><h2>Minha conta</h2><div className="settings-slab">
      <div className="account-summary"><span className="account-avatar">{snapshot.access.displayName?.slice(0, 1).toUpperCase() ?? "S"}</span><div><h3>{snapshot.access.displayName ?? "Conta conectada"}</h3><p>{snapshot.access.email ?? "Identidade protegida pelo Runtime"}</p></div><span className="neutral-badge">{snapshot.access.plan ?? "Plano não informado"}</span></div>
      <div className="preference-row"><div><strong>Acesso ao produto</strong><p>Identidade e assinatura são verificações independentes.</p></div><span className={snapshot.access.state === "active" ? "access-confirmed" : "neutral-badge"}><Glyph name="shield" size={15} />{snapshot.access.state === "active" ? "Assinatura ativa" : "Acesso não confirmado"}</span></div>
      <div className="preference-row"><div><strong>Validade informada</strong><p>{formatRuntimeTimestamp(snapshot.access.expiresAt, { fallback: "O Runtime não informou uma data de expiração válida." })}</p></div><button className="button button-secondary" type="button" onClick={onRefresh} disabled={busy}>{busy ? "Atualizando…" : "Atualizar estado"}</button></div>
      <div className="preference-row"><div><strong>Gerenciar assinatura</strong><p>Abre sua conta no site do Simplicio.</p></div><button className="button button-secondary" type="button" onClick={onSubscribe} disabled={busy}>Gerenciar plano<Glyph name="external" size={15} /></button></div>
      <div className="preference-row"><div><strong>Sair deste computador</strong><p>O Runtime remove o login local e tenta revogar a sessão remota. Seus projetos não são apagados.</p></div><button className="button button-secondary" type="button" onClick={onLogout} disabled={busy || logoutBusy}>{logoutBusy ? "Saindo…" : "Sair da conta"}</button></div>
    </div></section>}
    {section !== "account" && <>
      <section className="settings-section"><h2>Runtime local</h2><div className="settings-slab">
        <div className="preference-row"><div><strong>{runtime.label}</strong><p>Versão {snapshot.runtime.version || "não informada"} · transporte {snapshot.runtime.transport}</p></div><button className="button button-secondary" type="button" onClick={onRefresh} disabled={busy}><Glyph name="refresh" size={16} />{busy ? "Atualizando…" : "Atualizar estado"}</button></div>
        <div className="preference-row"><div><strong>Leitura do snapshot</strong><p>{formatRuntimeTimestamp(snapshot.generatedAt)}</p></div><span className="neutral-badge">{snapshot.source === "runtime" ? "Runtime" : "Demonstração"}</span></div>
        <div className="preference-row"><div><strong>Conexões MCP</strong><p>Um registro não comprova uma sessão ativa.</p></div><span>{runtime.connected} confirmadas</span></div>
      </div></section>
      <section className="settings-section"><h2>Exportar diagnóstico</h2><div className="settings-slab"><div className="preference-row"><div><strong>Relatório sem dados sensíveis</strong><p>Omite email, caminhos pessoais, prompts, configurações, credenciais, skills e ledger bruto. Salvo em Downloads sem substituir arquivos.</p></div><button className="button button-secondary" type="button" onClick={() => void download()} disabled={exporting}>{exporting ? "Exportando…" : "Exportar diagnóstico"}</button></div></div>
        {exported && <p className="export-feedback" role="status">Exportado para {exported}</p>}{exportError && <p className="inline-error" role="alert">{exportError}</p>}
      </section>
    </>}
    <p className="settings-footnote"><Glyph name="lock" size={15} />O Desktop não armazena senhas ou tokens de providers na interface.</p>
  </div>;
}
