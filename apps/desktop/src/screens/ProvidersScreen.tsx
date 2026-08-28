import { useMemo, useState } from "react";
import type { DesktopSnapshot, ProviderConnection, ProviderState } from "../contracts";
import { Glyph } from "../components/Brand";

const stateCopy: Record<ProviderState, string> = {
  connected: "Conectado",
  detected: "Detectado",
  needs_attention: "Requer atenção",
  not_installed: "Não instalado",
};

const actionCopy: Record<ProviderState, string> = {
  connected: "Ver detalhes",
  detected: "Conectar",
  needs_attention: "Corrigir conexão",
  not_installed: "Como instalar",
};

function ProviderCard({ provider }: { provider: ProviderConnection }) {
  return (
    <article className={`provider-card state-${provider.state}`}>
      <div className="provider-card-top">
        <div className={`provider-logo provider-${provider.id}`}>{provider.name.slice(0, 2).toUpperCase()}</div>
        <span className={`provider-state ${provider.state}`}><span className="status-dot" />{stateCopy[provider.state]}</span>
      </div>
      <div className="provider-card-copy">
        <h3>{provider.name}</h3>
        <p>{provider.detail}</p>
      </div>
      <div className="provider-tags">
        <span>{provider.protocol}</span>
        <span>{provider.kind === "agent" ? "Agente" : "Editor"}</span>
        {provider.version && <span>v{provider.version}</span>}
      </div>
      {provider.account && <p className="provider-account">{provider.account}</p>}
      <button className="provider-action" type="button">
        {actionCopy[provider.state]} <Glyph name="arrow" size={16} />
      </button>
    </article>
  );
}

export function ProvidersScreen({ snapshot }: { snapshot: DesktopSnapshot }) {
  const [filter, setFilter] = useState<"all" | "ready" | "available">("all");
  const ordered = useMemo(() => {
    const rank: Record<ProviderState, number> = { connected: 0, needs_attention: 1, detected: 2, not_installed: 3 };
    return [...snapshot.providers]
      .filter((provider) => {
        if (filter === "ready") return provider.state === "connected" || provider.state === "needs_attention";
        if (filter === "available") return provider.state === "detected" || provider.state === "not_installed";
        return true;
      })
      .sort((a, b) => rank[a.state] - rank[b.state]);
  }, [filter, snapshot.providers]);

  const connected = snapshot.providers.filter((provider) => provider.state === "connected").length;
  const detected = snapshot.providers.filter((provider) => provider.state === "detected").length;
  const attention = snapshot.providers.filter((provider) => provider.state === "needs_attention").length;

  return (
    <div className="page providers-page">
      <section className="page-heading providers-heading">
        <div>
          <span className="eyebrow">Conexões</span>
          <h1>Providers</h1>
          <p>{connected} conectados · {detected} detectados</p>
        </div>
        <button className="button button-primary" type="button"><Glyph name="refresh" size={17} /> Verificar</button>
      </section>

      <section className="provider-summary" aria-label="Resumo das conexões">
        <div><strong>{connected}</strong><span>conectados</span></div>
        <div><strong>{detected}</strong><span>detectados</span></div>
        <div className={attention ? "summary-attention" : ""}><strong>{attention}</strong><span>requer atenção</span></div>
        <p><Glyph name="shield" size={18} /> Credenciais permanecem no provider.</p>
      </section>

      <div className="provider-toolbar">
        <div className="segmented-control" role="group" aria-label="Filtrar providers">
          <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")} type="button">Todos</button>
          <button className={filter === "ready" ? "active" : ""} onClick={() => setFilter("ready")} type="button">Em uso</button>
          <button className={filter === "available" ? "active" : ""} onClick={() => setFilter("available")} type="button">Disponíveis</button>
        </div>
        <span className="provider-count">{ordered.length} providers</span>
      </div>

      <section className="provider-grid">
        {ordered.map((provider) => <ProviderCard provider={provider} key={provider.id} />)}
      </section>

      <section className="provider-principle">
        <div className="principle-icon"><Glyph name="spark" size={24} /></div>
        <div>
          <span className="eyebrow">Status confiável</span>
          <h2>Detectado ≠ conectado</h2>
          <p>O verde exige handshake válido.</p>
        </div>
        <button className="text-button" type="button">Entender os estados <Glyph name="arrow" size={16} /></button>
      </section>
    </div>
  );
}
