import type { DesktopSnapshot } from "../contracts";
import { Glyph } from "../components/Brand";

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

function downloadDiagnostic(snapshot: DesktopSnapshot) {
  if (typeof document === "undefined") return;
  const payload = JSON.stringify(redactedDiagnostic(snapshot), null, 2);
  const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "simplicio-diagnostic.json";
  link.click();
  URL.revokeObjectURL(url);
}

export function SettingsScreen({
  snapshot,
  busy,
  onRefresh,
  onSubscribe,
  onLogout,
  logoutBusy,
}: {
  snapshot: DesktopSnapshot;
  busy: boolean;
  onRefresh: () => void;
  onSubscribe: () => void;
  onLogout: () => void;
  logoutBusy: boolean;
}) {
  return (
    <div className="page secondary-page">
      <section className="page-heading">
        <div>
          <span className="eyebrow">Preferências</span>
          <h1>Configurações</h1>
          <p>Conta, atualização e diagnóstico sem expor dados sensíveis.</p>
        </div>
      </section>
      <section className="settings-grid">
        <article className="panel settings-card">
          <div className="settings-card-heading"><Glyph name="settings" size={20} /><div><span className="eyebrow">Conta</span><h2>{snapshot.access.plan ?? "Simplicio"}</h2></div></div>
          <dl>
            <div><dt>Acesso</dt><dd>{snapshot.access.state}</dd></div>
            <div><dt>Identidade</dt><dd>{snapshot.access.identityKnown ? "confirmada" : "não disponível"}</dd></div>
            <div><dt>Expiração</dt><dd>{snapshot.access.expiresAt ? new Date(snapshot.access.expiresAt).toLocaleDateString("pt-BR") : "não informada"}</dd></div>
          </dl>
          <button className="button button-secondary button-wide" type="button" onClick={onSubscribe}>Gerenciar plano</button>
          <button className="button button-secondary button-wide" type="button" onClick={onLogout} disabled={logoutBusy}>
            {logoutBusy ? "Saindo…" : "Sair da conta"}
          </button>
        </article>
        <article className="panel settings-card">
          <div className="settings-card-heading"><Glyph name="activity" size={20} /><div><span className="eyebrow">Diagnóstico</span><h2>Estado do Runtime</h2></div></div>
          <dl>
            <div><dt>Versão</dt><dd>{snapshot.runtime.version || "indisponível"}</dd></div>
            <div><dt>Transporte</dt><dd>{snapshot.runtime.transport}</dd></div>
            <div><dt>Última leitura</dt><dd>{snapshot.runtime.lastReceiptAt ? new Date(snapshot.runtime.lastReceiptAt).toLocaleString("pt-BR") : "sem recibo"}</dd></div>
          </dl>
          <div className="settings-actions">
            <button className="button button-secondary" type="button" onClick={onRefresh} disabled={busy}>{busy ? "Atualizando…" : "Atualizar estado"}</button>
            <button className="button button-secondary" type="button" onClick={() => downloadDiagnostic(snapshot)}>Exportar diagnóstico</button>
          </div>
          <p className="settings-note">O export omite email, caminhos, prompts, configurações, credenciais, skills e ledger bruto.</p>
        </article>
      </section>
      <section className="panel settings-safety">
        <Glyph name="lock" size={18} />
        <div><span className="eyebrow">Privacidade</span><strong>Dados locais sob controle</strong><p>O logout revoga a sessão no Runtime e limpa as credenciais locais; nenhum token é mantido nesta tela.</p></div>
      </section>
    </div>
  );
}
