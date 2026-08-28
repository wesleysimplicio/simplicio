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

export function SignInScreen() {
  return (
    <div className="access-layout">
      <section className="access-story">
        <Brand />
        <div className="access-story-copy">
          <span className="eyebrow">Simplicio Desktop</span>
          <h1>Seu Runtime,<br />pronto para usar.</h1>
          <p>Codex, Claude e seus editores no mesmo lugar.</p>
        </div>
        <div className="access-proof-grid">
          <article>
            <span>✓</span>
            <strong>Login seguro</strong>
          </article>
          <article>
            <span>✓</span>
            <strong>Runtime local</strong>
          </article>
          <article>
            <span>✓</span>
            <strong>Providers conectados</strong>
          </article>
        </div>
      </section>

      <section className="access-panel" aria-labelledby="login-title">
        <div className="access-card">
          <div className="access-card-icon"><Glyph name="shield" size={25} /></div>
          <span className="eyebrow">Bem-vindo</span>
          <h2 id="login-title">Entre no Simplicio</h2>
          <p>Use sua conta SimpleTI.</p>
          <button className="button button-primary button-wide" type="button">
            <span className="google-mark">G</span>
            Continuar com Google
            <Glyph name="arrow" />
          </button>
          <div className="access-divider"><span>incluído</span></div>
          <ul className="access-checklist">
            <li><Glyph name="check" size={17} /> Assinatura verificada</li>
            <li><Glyph name="check" size={17} /> Runtime preparado</li>
            <li><Glyph name="check" size={17} /> Providers validados</li>
          </ul>
          <p className="fine-print">
            O login abre no navegador. Nenhuma senha passa pelo app.
          </p>
        </div>
      </section>
    </div>
  );
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

export function AccessGate({ state, email }: { state: "inactive" | "unknown"; email?: string }) {
  const content = accessContent[state];
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
          <button className="button button-primary" type="button">{content.primary}<Glyph name="arrow" /></button>
          <button className="button button-secondary" type="button">{content.secondary}</button>
        </div>
        <div className="locked-safe-actions">
          <span><Glyph name="shield" size={17} /> Sempre disponíveis</span>
          <strong>Conta · cobrança · diagnóstico</strong>
        </div>
      </section>
      <p className="locked-footer">Runtime desabilitado até a confirmação.</p>
    </div>
  );
}
