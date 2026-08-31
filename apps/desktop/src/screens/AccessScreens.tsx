import { useEffect, useRef, useState } from "react";
import type { AccessState } from "../contracts";
import { Brand, Glyph } from "../components/Brand";

export function LoadingScreen() {
  return (
    <div className="boot-screen">
      <Brand />
      <div className="boot-orbit" aria-hidden="true">
        <span />
      </div>
      <p>Conectando ao Runtime local…</p>
    </div>
  );
}

export function SignInScreen({ busy, error, onLogin, initialStep = "welcome" }:
  { busy: boolean; error: string | null; onLogin: () => void; initialStep?: "welcome" | "login" }) {
  const [step, setStep] = useState(initialStep);
  const primaryAction = useRef<HTMLButtonElement>(null);
  useEffect(() => { primaryAction.current?.focus(); }, [step]);
  const platform = typeof navigator === "undefined" ? "Desktop"
    : /Mac/.test(navigator.platform) ? "Mac" : /Win/.test(navigator.platform) ? "Windows" : "Linux";
  return <div className="access-layout entry-flow">
    <header className="entry-header"><Brand />{step === "login" && <button className="text-button" type="button" disabled={busy} onClick={() => setStep("welcome")}><Glyph name="back" size={16} />Voltar</button>}</header>
    {step === "welcome" ? <section className="entry-welcome access-story" aria-labelledby="welcome-title">
      <img className="entry-mark" src="/icon.png" width="88" height="88" alt="" />
      <h1 id="welcome-title">Simplicio <em>para {platform}</em></h1>
      <p>Seu Runtime, pronto para trabalhar com você.</p>
      <button ref={primaryAction} className="button entry-primary" type="button" onClick={() => setStep("login")}>Começar<Glyph name="arrow" size={18} /></button>
      <span className="entry-caption">Projetos, agentes e economia. No seu computador.</span>
    </section> : <section className="entry-login access-panel" aria-labelledby="login-title">
      <h1 id="login-title">Entre no Simplicio</h1>
      <div className="entry-login-card">
        <p className="entry-account-copy">Conecte sua conta SimpleTI para continuar.</p>
        <button ref={primaryAction} className="button entry-google" type="button" onClick={onLogin} disabled={busy} aria-busy={busy}>
          <span className="google-mark" aria-hidden="true">G</span>{busy ? "Aguardando navegador…" : "Continuar com Google"}
        </button>
        {busy && <p className="entry-wait" role="status"><span className="setup-spinner" aria-hidden="true" />Conclua o login no navegador. O app continua quando o Runtime confirmar sua sessão.</p>}
        {error && <p className="action-error" role="alert">{error}</p>}
        <div className="entry-login-note"><Glyph name="lock" size={16} /><p>O login abre no navegador. Nenhuma senha passa pelo app.</p></div>
        <p className="entry-caption">Sua identidade e assinatura são verificadas separadamente pelo Runtime.</p>
      </div>
    </section>}
    <footer className="entry-footer"><Glyph name="shield" size={14} />Autenticação pelo Runtime · Dados locais sob seu controle</footer>
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
        {state === "unknown" && loginBusy && <p className="entry-wait" role="status">Conclua o login no navegador. O acesso permanece desconhecido até o Runtime confirmar sua sessão.</p>}
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
