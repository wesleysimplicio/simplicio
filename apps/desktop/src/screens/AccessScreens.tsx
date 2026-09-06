import { useEffect, useRef, useState } from "react";
import type { AccessState } from "../contracts";
import { Brand, Glyph } from "../components/Brand";
import type { RuntimeInstallResult } from "../runtime_install";
import type { PreparationResult } from "../runtime_preparation_result";

export function LoadingScreen() {
  return (
    <div className="boot-screen">
      <Brand />
      <div className="boot-orbit" aria-hidden="true">
        <span />
      </div>
    </div>
  );
}

export type RuntimeInstallPhase = "idle" | "installing" | "preparing" | "validating" | "failed";

const runtimeInstallSteps = [
  ["Validar componente", "Conferir o Runtime e as dependências empacotadas."],
  ["Instalar Runtime", "Publicar a cópia local com segurança."],
  ["Verificar instalação", "Confirmar integridade e versão."],
  ["Preparar ambiente", "Detectar Python; preparar memória, seeds, migrations e clientes detectados."],
  ["Concluir", "Ler o estado atual antes do login."],
] as const;

function runtimeInstallStepStates(phase: RuntimeInstallPhase, receipt?: RuntimeInstallResult) {
  // The native operation confirms these three steps together in its receipt.
  // Do not invent a current or failed substep while that receipt is absent.
  if (phase === "installing") return ["awaiting", "awaiting", "awaiting", "pending", "pending"] as const;
  if (phase === "preparing") return ["complete", "complete", "complete", "running", "pending"] as const;
  if (phase === "validating") return ["complete", "complete", "complete", "complete", "running"] as const;
  if (phase === "failed") {
    return receipt
      ? (["complete", "complete", "complete", "unconfirmed", "unconfirmed"] as const)
      : (["unconfirmed", "unconfirmed", "unconfirmed", "pending", "pending"] as const);
  }
  return ["pending", "pending", "pending", "pending", "pending"] as const;
}

export function RuntimeInstallScreen({ phase, receipt, preparation, error, onInstall, reconciliationRequired, onReconcile }: {
  phase: RuntimeInstallPhase;
  receipt?: RuntimeInstallResult;
  preparation?: PreparationResult;
  error: string | null;
  onInstall: () => void;
  reconciliationRequired?: boolean;
  onReconcile?: () => void;
}) {
  const states = runtimeInstallStepStates(phase, receipt);
  const busy = phase === "installing" || phase === "preparing" || phase === "validating";
  // Native operations return receipts, not fractional progress events.
  const progress = phase === "validating" ? 80 : phase === "preparing" || (phase === "failed" && receipt) ? 60 : phase === "installing" ? undefined : 0;
  const status = reconciliationRequired
    ? "Consulte o estado da instalação anterior."
    : phase === "installing"
      ? "Instalando Runtime…"
      : phase === "preparing"
        ? "Preparando ambiente local…"
        : phase === "validating"
          ? "Confirmando estado…"
          : phase === "failed"
            ? "Preparação não concluída."
            : "Pronto.";

  if (phase === "idle" && !reconciliationRequired && !error) {
    return <div className="access-layout entry-flow">
      <section className="entry-welcome access-story" aria-label="Instalar Simplicio">
        <img className="entry-mark" src="/icon.png" width="88" height="88" alt="Simplicio" />
        <button className="button entry-primary" type="button" onClick={onInstall}>Install Now<Glyph name="arrow" size={18} /></button>
      </section>
    </div>;
  }

  return <div className="setup-layout runtime-install-layout">
    <header className="entry-header"><Brand /></header>
    <div className="runtime-install-progress">
      <progress className="setup-progress" max={100} value={progress} aria-label="Progresso da preparação do Runtime" />
    </div>
    <main className="setup-main">
      <section className="setup-body runtime-install-body" aria-labelledby="runtime-install-title">
        <div className={`setup-heading${phase === "failed" ? " is-failed" : ""}`}>
          <span className="eyebrow">INSTALAÇÃO</span>
          <h1 id="runtime-install-title">Preparando Simplicio</h1>
        </div>
        <p className="runtime-install-status" role="status">{status}</p>
        <ol className="setup-steps">
          {runtimeInstallSteps.map(([label, detail], index) => {
            const state = states[index];
            return <li key={label} data-state={state}>
              <span className="setup-step-icon">
                {state === "complete" ? <Glyph name="check" size={15} />
                  : state === "running" ? <span className="setup-spinner" aria-hidden="true" /> : index + 1}
              </span>
              <span><strong>{label}</strong><p>{detail}</p></span>
              <span className="setup-step-status">{state === "complete" ? "Concluído" : state === "running" ? "Em andamento" : state === "awaiting" ? "Aguardando confirmação" : state === "unconfirmed" ? "Não confirmada" : "Pendente"}</span>
            </li>;
          })}
        </ol>
        {receipt && <p className="runtime-install-receipt"><Glyph name="shield" size={16} />Runtime {receipt.runtime.version} validado</p>}
        {preparation && <section className="runtime-preparation-summary" aria-label="Ambiente preparado">
          <h2>Ambiente preparado</h2>
          <ul>
            <li><span>Dependências</span><strong>Empacotadas · pronto</strong></li>
            <li><span>Python</span><strong>{preparation.python.status === "detected" ? `Detectado · ${preparation.python.version}` : preparation.python.status === "unavailable" ? "Indisponível · Runtime nativo ativo" : "Não detectado · não necessário"}</strong></li>
            <li><span>Memória, seeds e migrations</span><strong>{preparation.memory.items.toLocaleString("pt-BR")} itens · {preparation.memory.skills.toLocaleString("pt-BR")} skills · {preparation.memory.migrations} migrations · pronto</strong></li>
            <li><span>Clientes detectados</span><strong>{preparation.clients.configured} configurados · {preparation.clients.skipped} ignorados</strong></li>
          </ul>
        </section>}
        {error && <p className="action-error" role="alert">{error}</p>}
      </section>
    </main>
    <div className="setup-actionbar">
      <div className="setup-footer-inner">
        {reconciliationRequired && onReconcile && <button className="button button-secondary" type="button" onClick={onReconcile} disabled={busy} aria-busy={busy}>
          {busy ? "Consultando…" : "Consultar estado"}
        </button>}
        <button className="button button-primary" type="button" onClick={onInstall} disabled={busy || reconciliationRequired} aria-busy={busy}>
          {busy ? "Preparando…" : phase === "failed" ? "Tentar novamente" : "Install Now"}
          {!busy && <Glyph name="arrow" size={17} />}
        </button>
      </div>
    </div>
  </div>;
}

export function SignInScreen({ busy, error, onLogin, initialStep = "welcome" }:
  { busy: boolean; error: string | null; onLogin: () => void; initialStep?: "welcome" | "login" }) {
  const [step, setStep] = useState(initialStep);
  const primaryAction = useRef<HTMLButtonElement>(null);
  useEffect(() => { primaryAction.current?.focus(); }, [step]);
  return <div className="access-layout entry-flow">
    {step === "welcome" ? <section className="entry-welcome access-story" aria-label="Bem-vindo ao Simplicio">
      <img className="entry-mark" src="/icon.png" width="88" height="88" alt="Simplicio" />
      <button ref={primaryAction} className="button entry-primary" type="button" onClick={() => setStep("login")}>Começar<Glyph name="arrow" size={18} /></button>
    </section> : <section className="entry-login access-panel" aria-label="Entrar no Simplicio">
      <img className="entry-mark" src="/icon.png" width="88" height="88" alt="Simplicio" />
      <div className="entry-login-card">
        <button ref={primaryAction} className="button entry-google" type="button" onClick={onLogin} disabled={busy} aria-busy={busy}>
          <svg className="google-mark" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.88h5.38a4.6 4.6 0 0 1-2 3.02v2.51h3.24c1.9-1.75 2.98-4.33 2.98-7.36Z" />
            <path fill="#34A853" d="M12 22c2.7 0 4.96-.9 6.62-2.41l-3.24-2.51c-.9.6-2.05.97-3.38.97-2.6 0-4.81-1.76-5.6-4.13H3.06v2.59A10 10 0 0 0 12 22Z" />
            <path fill="#FBBC05" d="M6.4 13.92a6 6 0 0 1 0-3.84V7.49H3.06a10 10 0 0 0 0 9.02l3.34-2.59Z" />
            <path fill="#EA4335" d="M12 5.95c1.47 0 2.79.51 3.82 1.51l2.87-2.87A9.6 9.6 0 0 0 12 2a10 10 0 0 0-8.94 5.49l3.34 2.59C7.19 7.71 9.4 5.95 12 5.95Z" />
          </svg>{busy ? "Aguardando navegador…" : "Continuar com Google"}
        </button>
        {error && <p className="action-error" role="alert">{error}</p>}
      </div>
    </section>}
  </div>;
}

const accessContent: Record<Exclude<AccessState, "signed_out" | "active">, {
  eyebrow: string;
  title: string;
  description: string;
  primary: string;
  secondary: string;
}> = {
  inactive: {
    eyebrow: "Acesso necessário",
    title: "Ative o Simplicio",
    description: "Sua conta está conectada, mas a assinatura não está ativa.",
    primary: "Ver planos",
    secondary: "Verificar novamente",
  },
  unknown: {
    eyebrow: "Não foi possível verificar",
    title: "Tente novamente",
    description: "O acesso continua desconhecido; não o tratamos como assinatura inativa.",
    primary: "Tentar novamente",
    secondary: "Abrir diagnóstico",
  },
};

export function AccessGate({
  state,
  email,
  busy,
  error,
  onRefresh,
  onLogin,
  loginBusy = false,
  onSubscribe,
  onLogout,
  logoutBusy = false,
}: {
  state: "inactive" | "unknown";
  email?: string | null;
  busy: boolean;
  error: string | null;
  onRefresh: () => void;
  onLogin?: () => void;
  loginBusy?: boolean;
  onSubscribe?: () => void;
  onLogout?: () => void;
  logoutBusy?: boolean;
}) {
  const content = accessContent[state];
  const [showDiagnostic, setShowDiagnostic] = useState(false);
  const actionBusy = busy || loginBusy || logoutBusy;
  return (
    <div className="locked-layout">
      <div className="locked-glow" aria-hidden="true" />
      <div className="locked-header">
        <Brand />
        {email && <span className="locked-account">{email}</span>}
      </div>
      <section className="locked-card">
        <div className="lock-illustration">
          <span className="lock-ring ring-one" />
          <span className="lock-ring ring-two" />
          <div><Glyph name={state === "inactive" ? "lock" : "refresh"} size={31} /></div>
        </div>
        <span className="eyebrow">{content.eyebrow}</span>
        <h1>{content.title}</h1>
        <p>{content.description}</p>
        <div className="locked-actions">
          <button
            className="button button-primary"
            type="button"
            onClick={state === "inactive" ? onSubscribe : onRefresh}
            disabled={actionBusy}
          >
            {actionBusy ? "Aguarde…" : content.primary}<Glyph name="arrow" />
          </button>
          {state === "inactive" && (
            <button className="button button-secondary" type="button" onClick={onRefresh} disabled={actionBusy}>
              {content.secondary}
            </button>
          )}
          {state === "unknown" && onLogin && (
            <button className="button button-secondary" type="button" onClick={onLogin} disabled={actionBusy} aria-busy={loginBusy}>
              {loginBusy ? "Aguardando navegador…" : "Entrar ou reconectar"}
            </button>
          )}
          {state === "unknown" && (
            <button className="button button-secondary" type="button" onClick={() => setShowDiagnostic((current) => !current)}>
              {showDiagnostic ? "Fechar diagnóstico" : content.secondary}
            </button>
          )}
          {onLogout && (
            <button className="button button-secondary" type="button" onClick={onLogout} disabled={actionBusy} aria-busy={logoutBusy}>
              {logoutBusy ? "Saindo…" : "Sair da conta"}
            </button>
          )}
        </div>
        {error && <p className="action-error" role="alert">{error}</p>}
        {showDiagnostic && state === "unknown" && (
          <div className="access-diagnostic" aria-live="polite">
            <strong>Estado de acesso desconhecido</strong>
            <p>A comunicação com o Runtime ou com o serviço de entitlement falhou. Tente novamente; nenhuma cobrança ou assinatura foi alterada.</p>
          </div>
        )}
        <div className="locked-safe-actions">
          <span><Glyph name="shield" size={17} /> Sempre disponíveis</span>
          <strong>Conta · cobrança · diagnóstico</strong>
        </div>
      </section>
      <p className="locked-footer">Runtime desabilitado até a confirmação.</p>
    </div>
  );
}
