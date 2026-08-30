import { useMemo, useState } from "react";
import type { DesktopSnapshot, ProviderConnection, ProviderState } from "../contracts";
import { Glyph } from "../components/Brand";
import { providerRegistry } from "../provider_registry";
import { t } from "../i18n";
import { IntegrationSetup } from "../components/IntegrationSetup";

const stateCopy: Record<ProviderState, string> = {
  connected: t("provider.connected"),
  registered: t("provider.registered"),
  detected: t("provider.detected"),
  needs_attention: t("provider.needs_attention"),
  not_installed: t("provider.not_installed"),
};

function ProviderCard({ provider, onSelect }: { provider: ProviderConnection; onSelect: () => void }) {
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
      <button className="provider-action" type="button" onClick={onSelect}>
        Ver detalhes <Glyph name="arrow" size={16} />
      </button>
    </article>
  );
}

export function ProvidersScreen({
  snapshot,
  busy,
  repairing,
  onRefresh,
  onRepair,
}: {
  snapshot: DesktopSnapshot;
  busy: boolean;
  repairing: boolean;
  onRefresh: () => void;
  onRepair: (digest: string) => Promise<boolean>;
}) {
  const [filter, setFilter] = useState<"all" | "ready" | "available">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showStateGuide, setShowStateGuide] = useState(false);
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
  const registered = canonical.filter((provider) => provider.state === "registered").length;
  const detected = canonical.filter((provider) => provider.state === "detected").length;
  const attention = canonical.filter((provider) => provider.state === "needs_attention").length;
  const selected = canonical.find((provider) => provider.id === selectedId) ?? null;

  return (
    <div className="page providers-page">
      <section className="page-heading providers-heading">
        <div>
          <span className="eyebrow">Conexões</span>
          <h1>Providers</h1>
          <p>Harnesses, IDEs e ADEs conectados ao Simplicio MCP. Registro não comprova uma sessão ativa.</p>
          <p>{connected} conectados · {registered} registrados · {detected} detectados</p>
        </div>
        <div className="provider-heading-actions">
          <button className="button button-primary" type="button" onClick={onRefresh} disabled={busy}>
            <Glyph name="refresh" size={17} /> {busy && !repairing ? "Verificando…" : "Verificar"}
          </button>
        </div>
      </section>

      <IntegrationSetup busy={busy} onApply={onRepair} />

      <section className="provider-summary" aria-label="Resumo das conexões">
        <div><strong>{connected}</strong><span>conectados</span></div>
        <div><strong>{registered}</strong><span>registrados</span></div>
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
        {ordered.map((provider) => (
          <ProviderCard provider={provider} key={provider.id} onSelect={() => setSelectedId(provider.id)} />
        ))}
      </section>

      {selected && (
        <section className="panel provider-detail" aria-live="polite">
          <div>
            <span className="eyebrow">{stateCopy[selected.state]}</span>
            <h2>{selected.name}</h2>
            <p>{selected.detail}</p>
          </div>
          <dl>
            <div><dt>Instalação</dt><dd>{selected.installState}</dd></div>
            <div><dt>Registro</dt><dd>{selected.registrationState}</dd></div>
            <div><dt>Handshake</dt><dd>{selected.handshakeState}</dd></div>
            <div><dt>Frescor</dt><dd>{selected.freshness}</dd></div>
          </dl>
          <button className="text-button" type="button" onClick={() => setSelectedId(null)}>Fechar detalhes</button>
        </section>
      )}

      <section className="provider-principle">
        <div className="principle-icon"><Glyph name="spark" size={24} /></div>
        <div>
          <span className="eyebrow">Status confiável</span>
          <h2>Detectado ≠ conectado</h2>
          <p>O verde exige handshake válido.</p>
        </div>
        <button className="text-button" type="button" aria-expanded={showStateGuide} onClick={() => setShowStateGuide((current) => !current)}>
          {showStateGuide ? "Ocultar estados" : "Entender os estados"} <Glyph name="arrow" size={16} />
        </button>
      </section>

      {showStateGuide && (
        <section className="panel provider-state-guide" aria-live="polite">
          <strong>Conectado</strong><span>handshake atual e registro válido</span>
          <strong>Registrado</strong><span>configuração presente, handshake ainda não confirmado</span>
          <strong>Detectado</strong><span>aplicativo encontrado, aguardando registro</span>
          <strong>Requer atenção</strong><span>configuração antiga, falha ou incompatibilidade detectada</span>
          <strong>Não instalado</strong><span>nenhuma instalação verificável encontrada</span>
        </section>
      )}
    </div>
  );
}
