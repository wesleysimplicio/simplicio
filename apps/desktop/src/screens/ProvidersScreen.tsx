import { useMemo, useState } from "react";
import type { DesktopSnapshot, ProviderConnection, ProviderState } from "../contracts";
import { Glyph } from "../components/Brand";
import { providerRegistry } from "../provider_registry";

const stateCopy: Record<ProviderState, string> = {
  connected: "Conectado",
  registered: "Registrado",
  detected: "Detectado",
  needs_attention: "Requer atenção",
  not_installed: "Não instalado",
};

const actionCopy: Record<ProviderState, string> = {
  connected: "Ver detalhes",
  registered: "Verificar",
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
      </div>
      <span className="provider-action provider-action-static">
        {actionCopy[provider.state]} <Glyph name="arrow" size={16} />
      </span>
    </article>
  );
}

export function ProvidersScreen({
  snapshot,
  busy,
  onRefresh,
}: {
  snapshot: DesktopSnapshot;
  busy: boolean;
  onRefresh: () => void;
}) {
  const [filter, setFilter] = useState<"all" | "ready" | "available">("all");
  const ordered = useMemo(() => {
    return providerRegistry(snapshot.providers)
      .filter((provider) => {
        if (filter === "ready") return provider.state === "connected" || provider.state === "needs_attention";
        if (filter === "available") return provider.state === "registered" || provider.state === "detected" || provider.state === "not_installed";
        return true;
      })
  }, [filter, snapshot.providers]);

  const canonical = providerRegistry(snapshot.providers);
  const connected = canonical.filter((provider) => provider.state === "connected").length;
  const detected = canonical.filter((provider) => provider.state === "detected" || provider.state === "registered").length;
  const attention = canonical.filter((provider) => provider.state === "needs_attention").length;

  return (
    <div className="page providers-page">
      <section className="page-heading providers-heading">
        <div>
          <span className="eyebrow">Conexões</span>
          <h1>Providers</h1>
          <p>{connected} conectados · {detected} detectados</p>
        </div>
        <button className="button button-primary" type="button" onClick={onRefresh} disabled={busy}>
          <Glyph name="refresh" size={17} /> {busy ? "Verificando…" : "Verificar"}
        </button>
      </section>

      <section className="provider-summary" aria-label="Resumo das conexões">
        <div><strong>{connected}</strong><span>conectados</span></div>
        <div><strong>{detected}</strong><span>detectados</span></div>
        <div className={attention ? "summary-attention" : ""}><strong>{attention}</strong><span>requer atenção</span></div>
        <p><Glyph name="shield" size={18} /> Credenciais permanecem no provider.</p>
      </section>

      <div className="provider-toolbar">
        <div className="segmented-control" role="group" aria-label="Filtrar providers">
          <button aria-pressed={filter === "all"} className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")} type="button">Todos</button>
          <button aria-pressed={filter === "ready"} className={filter === "ready" ? "active" : ""} onClick={() => setFilter("ready")} type="button">Em uso</button>
          <button aria-pressed={filter === "available"} className={filter === "available" ? "active" : ""} onClick={() => setFilter("available")} type="button">Disponíveis</button>
        </div>
        <span className="provider-count">{ordered.length} providers</span>
      </div>

      <section className="provider-grid" aria-label="Lista de providers">
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
