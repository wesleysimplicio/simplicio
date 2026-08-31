import { useMemo, useState } from "react";
import type { DesktopSnapshot, ProviderConnection, ProviderState } from "../contracts";
import { Glyph } from "../components/Brand";
import { providerRegistry } from "../provider_registry";
import { IntegrationSetup } from "../components/IntegrationSetup";
import { searchMatches } from "../workbench";

const stateCopy: Record<ProviderState, string> = {
  connected: "Conectado", registered: "Registrado", detected: "Detectado",
  needs_attention: "Requer atenção", not_installed: "Não instalado",
};

function ProviderRow({ provider }: { provider: ProviderConnection }) {
  const [expanded, setExpanded] = useState(false);
  return <article className={"provider-list-row state-" + provider.state}>
    <button className="provider-list-toggle" type="button" onClick={() => setExpanded((current) => !current)}
      aria-label={"Ver detalhes de " + provider.name} aria-expanded={expanded}>
      <span className={"provider-logo provider-" + provider.id}>{provider.name.slice(0, 2).toUpperCase()}</span>
      <span className="provider-list-copy"><strong>{provider.name}</strong><small>{provider.kind === "agent" ? "Agente / harness" : "IDE / ADE"} · {provider.protocol}</small></span>
      <span className={"provider-state " + provider.state}><span className="status-dot" />{stateCopy[provider.state]}</span>
      <span className={expanded ? "row-chevron expanded" : "row-chevron"}><Glyph name="chevron" size={16} /></span>
    </button>
    {expanded && <div className="provider-row-detail">
      <p>{provider.detail}</p>
      <dl>
        <div><dt>Aplicativo</dt><dd>{provider.installState === "installed" ? "Encontrado" : "Não encontrado"}</dd></div>
        <div><dt>Registro MCP</dt><dd>{provider.registrationState === "registered" ? "Configurado" : "Não configurado"}</dd></div>
        <div><dt>Handshake</dt><dd>{provider.handshakeState === "live" ? "Confirmado" : provider.handshakeState === "stale" ? "Desatualizado" : "Não verificado"}</dd></div>
        <div><dt>Frescor</dt><dd>{provider.freshness === "current" ? "Atual" : provider.freshness === "stale" ? "Desatualizado" : "Não informado"}</dd></div>
      </dl>
      <code>{provider.reasonCode}</code>
      <button className="text-button" type="button" onClick={() => setExpanded(false)}>Fechar detalhes</button>
    </div>}
  </article>;
}

export function ProvidersScreen({ snapshot, busy, repairing, onRefresh, onRepair, inventoryOnly = false }:
  { snapshot: DesktopSnapshot; busy: boolean; repairing: boolean; onRefresh: () => void; onRepair: (digest: string) => Promise<boolean>; inventoryOnly?: boolean }) {
  const [filter, setFilter] = useState<"all" | "installed" | "available" | "attention">("all");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"all" | "agent" | "editor">("all");
  const [showStateGuide, setShowStateGuide] = useState(false);
  const canonical = useMemo(() => providerRegistry(snapshot.providers), [snapshot.providers]);
  const ordered = canonical.filter((provider) => {
    if (!searchMatches(provider.name + " " + provider.protocol, query)) return false;
    if (kind !== "all" && provider.kind !== kind) return false;
    if (filter === "installed") return provider.installState === "installed";
    if (filter === "available") return provider.installState === "absent";
    if (filter === "attention") return provider.state === "needs_attention";
    return true;
  });
  const connected = canonical.filter((provider) => provider.state === "connected").length;
  const registered = canonical.filter((provider) => provider.registrationState === "registered").length;
  const installed = canonical.filter((provider) => provider.installState === "installed").length;

  return <div className="page providers-page">
    <section className="page-heading providers-heading">
      <div><h1>{inventoryOnly ? "Agentes e IDEs" : "Integrações MCP"}</h1><p>{inventoryOnly ? "Seus harnesses, IDEs e ADEs, em um só lugar." : "Configure seus clientes para usar o Simplicio MCP."} Registro e conexão são verificados separadamente.</p></div>
      <button className="button button-secondary" type="button" onClick={onRefresh} disabled={busy}><Glyph name="refresh" size={17} />{busy && !repairing ? "Verificando…" : "Verificar"}</button>
    </section>

    {!inventoryOnly && <IntegrationSetup busy={busy} onApply={onRepair} />}

    <section className="connection-overview" aria-label="Resumo das conexões">
      <div><Glyph name="monitor" size={18} /><span><strong>{installed}</strong> aplicativos detectados</span></div>
      <div><Glyph name="providers" size={18} /><span><strong>{registered}</strong> registros MCP</span></div>
      <div><span className={"status-dot " + (connected ? "online" : "offline")} /><span><strong>{connected}</strong> conexões confirmadas</span></div>
    </section>

    <section className="settings-section">
      <div className="section-title"><h2>{inventoryOnly ? "Inventário local" : "Clientes MCP"}</h2><span>{canonical.length} clientes no inventário</span></div>
      <div className="provider-toolbar">
        <label className="provider-search"><Glyph name="search" size={17} /><input type="search" aria-label="Buscar agentes e IDEs" placeholder="Buscar agentes e IDEs" value={query} onChange={(event) => setQuery(event.target.value)} maxLength={120} /></label>
        <select className="workbench-select" aria-label="Tipo de cliente" value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}><option value="all">Todos os tipos</option><option value="agent">Agentes / harnesses</option><option value="editor">IDEs / ADEs</option></select>
      </div>
      <div className="provider-filter-bar"><div className="segmented-control" role="group" aria-label="Filtrar providers">
        {(["all", "installed", "available", "attention"] as const).map((value) => <button type="button" key={value} aria-pressed={filter === value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{{ all: "Todos", installed: "Instalados", available: "Disponíveis", attention: "Atenção" }[value]}</button>)}
      </div><span>{ordered.length} resultados</span></div>
      <div className="settings-slab provider-list" aria-label="Lista de providers">
        {ordered.map((provider) => <ProviderRow key={provider.id} provider={provider} />)}
        {!ordered.length && <div className="inventory-empty" role="status"><Glyph name="search" size={24} /><h3>Nenhum cliente neste filtro</h3><p>Ajuste a busca ou atualize o inventário do Runtime.</p><button className="button button-secondary" type="button" onClick={() => { setQuery(""); setKind("all"); setFilter("all"); }}>Limpar filtros</button></div>}
      </div>
    </section>

    <section className="provider-evidence-note"><Glyph name="shield" size={19} /><div><strong>Detectado não significa conectado</strong><p>O estado conectado exige registro, handshake válido e informação atual. Credenciais ficam no provider.</p><button className="text-button" type="button" aria-expanded={showStateGuide} onClick={() => setShowStateGuide((current) => !current)}>{showStateGuide ? "Ocultar estados" : "Entender os estados"}<Glyph name="chevron" size={15} /></button></div></section>
    {showStateGuide && <section className="settings-slab provider-state-guide" aria-live="polite">
      <strong>Conectado</strong><span>handshake atual e registro válido</span>
      <strong>Registrado</strong><span>configuração presente, handshake ainda não confirmado</span>
      <strong>Detectado</strong><span>aplicativo encontrado, aguardando registro</span>
      <strong>Requer atenção</strong><span>configuração antiga, falha ou incompatibilidade detectada</span>
      <strong>Não instalado</strong><span>nenhuma instalação verificável encontrada</span>
    </section>}
  </div>;
}
